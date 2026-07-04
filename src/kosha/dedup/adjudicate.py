"""Ambiguous-band adjudication — the only LLM call in the dedup decision.

When two-threshold routing (M6 PR-2) cannot decide from the embedding score
alone, system_design §4.3 reserves a single judgment for the band: are the draft
and its nearest concept the *same*, *different*, or does the draft *mix* several
concepts and need a granularity split? The verdict carries a rationale that
feeds the audit log.

Two adjudicators ship, mirroring the provider split:

* :class:`LexicalAdjudicator` — a deterministic, offline default. It splits an
  over-scoped draft via the M3 granularity lint and otherwise calls same vs
  different by token-set (Jaccard) overlap. It is a coarse stand-in: a real
  model resolves the semantic paraphrases lexical overlap cannot — the
  documented dedup headroom (overview §6).
* :class:`GenerationAdjudicator` — the real LLM path. It prompts a configured
  :class:`~kosha.providers.base.GenerationProvider` and parses a one-word verdict.

Both adjudicators also expose :meth:`select`, which chooses *which* of several
ranked candidates a draft belongs to (or none -> CREATE) — the multi-candidate
surface the resolver uses when the embedding returns more than one neighbor.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from kosha.lint import granularity_warnings
from kosha.providers.base import GenerationProvider
from kosha.providers.tokens import tokenize


class Verdict(StrEnum):
    """An adjudicator's judgment for an ambiguous-band draft."""

    SAME = "same"
    DIFFERENT = "different"
    SPLIT = "split"


@dataclass(frozen=True)
class Adjudication:
    """A verdict plus the rationale recorded for the audit log."""

    verdict: Verdict
    rationale: str


@dataclass(frozen=True)
class CandidateConcept:
    """A ranked existing concept the adjudicator may select: id + indexed text."""

    concept_id: str
    text: str


@dataclass(frozen=True)
class Selection:
    """An adjudicator's choice among ranked candidates.

    ``concept_id`` is the chosen UPDATE target (``None`` for CREATE/SPLIT) and
    ``verdict`` says how to act: SAME -> UPDATE ``concept_id``, DIFFERENT ->
    CREATE, SPLIT -> granularity split. The rationale feeds the audit log.
    """

    concept_id: str | None
    verdict: Verdict
    rationale: str


class Adjudicator(Protocol):
    """Resolves an ambiguous-band draft against its nearest existing concept."""

    @property
    def name(self) -> str:
        """Stable identifier recorded in the audit log / report."""
        ...

    def adjudicate(self, draft_text: str, candidate_text: str) -> Adjudication:
        """Judge whether the draft is the same, different, or mixes concepts."""
        ...

    def select(
        self, draft_text: str, candidates: Sequence[CandidateConcept]
    ) -> Selection:
        """Choose which ranked candidate the draft belongs to, or none (CREATE)."""
        ...


class LexicalAdjudicator:
    """Deterministic offline adjudicator: granularity split + Jaccard same/different."""

    def __init__(self, same_threshold: float = 0.2) -> None:
        if not 0.0 <= same_threshold <= 1.0:
            raise ValueError("same_threshold must be in [0, 1]")
        self._same_threshold = same_threshold

    @property
    def name(self) -> str:
        return f"lexical-jaccard-{self._same_threshold:.2f}"

    def adjudicate(self, draft_text: str, candidate_text: str) -> Adjudication:
        warnings = granularity_warnings(draft_text)
        if warnings:
            return Adjudication(Verdict.SPLIT, f"granularity: {warnings[0]}")
        overlap = jaccard_overlap(draft_text, candidate_text)
        if overlap >= self._same_threshold:
            return Adjudication(
                Verdict.SAME, f"jaccard {overlap:.3f} >= {self._same_threshold:.2f}"
            )
        return Adjudication(
            Verdict.DIFFERENT, f"jaccard {overlap:.3f} < {self._same_threshold:.2f}"
        )

    def select(
        self, draft_text: str, candidates: Sequence[CandidateConcept]
    ) -> Selection:
        warnings = granularity_warnings(draft_text)
        if warnings:
            return Selection(None, Verdict.SPLIT, f"granularity: {warnings[0]}")
        if not candidates:
            return Selection(None, Verdict.DIFFERENT, "no candidates")
        scored = [(c, jaccard_overlap(draft_text, c.text)) for c in candidates]
        best, overlap = max(scored, key=lambda item: item[1])
        if overlap >= self._same_threshold:
            return Selection(
                best.concept_id,
                Verdict.SAME,
                f"best jaccard {overlap:.3f} >= {self._same_threshold:.2f} -> {best.concept_id}",
            )
        return Selection(
            None,
            Verdict.DIFFERENT,
            f"best jaccard {overlap:.3f} < {self._same_threshold:.2f}",
        )


class GenerationAdjudicator:
    """Real LLM adjudicator: prompt a generation provider and parse the verdict."""

    def __init__(self, provider: GenerationProvider) -> None:
        self._provider = provider

    @property
    def name(self) -> str:
        return f"generation:{self._provider.name}"

    def adjudicate(self, draft_text: str, candidate_text: str) -> Adjudication:
        query, context = build_adjudication_prompt(draft_text, candidate_text)
        generation = self._provider.generate(query, context)
        verdict = parse_verdict(generation.text)
        return Adjudication(verdict, f"{self.name}: {generation.text.strip()}")

    def select(
        self, draft_text: str, candidates: Sequence[CandidateConcept]
    ) -> Selection:
        if not candidates:
            return Selection(None, Verdict.DIFFERENT, f"{self.name}: no candidates")
        warnings = granularity_warnings(draft_text)
        if warnings:
            return Selection(None, Verdict.SPLIT, f"{self.name} granularity: {warnings[0]}")
        query, context = build_selection_prompt(draft_text, candidates)
        generation = self._provider.generate(query, context)
        return parse_selection(
            generation.text, [candidate.concept_id for candidate in candidates], self.name
        )


def build_adjudication_prompt(draft_text: str, candidate_text: str) -> tuple[str, str]:
    """Return the (query, context) pair posed to the generation provider."""
    query = (
        "Decide whether concept A and concept B describe the same concept, "
        "different concepts, or whether A mixes multiple concepts. "
        "Answer with exactly one word: same, different, or split."
    )
    context = f"Concept A:\n{draft_text}\n\nConcept B:\n{candidate_text}"
    return query, context


def parse_verdict(text: str) -> Verdict:
    """Parse a verdict keyword from a response (split > different > same)."""
    lowered = text.strip().lower()
    if Verdict.SPLIT.value in lowered:
        return Verdict.SPLIT
    if Verdict.DIFFERENT.value in lowered:
        return Verdict.DIFFERENT
    if Verdict.SAME.value in lowered:
        return Verdict.SAME
    raise ValueError(f"no verdict keyword in adjudicator response: {text!r}")


def build_selection_prompt(
    draft_text: str, candidates: Sequence[CandidateConcept]
) -> tuple[str, str]:
    """Return the (query, context) routing a note to the concept it is about.

    Routing is on topic identity, not agreement: a note that *contradicts* an
    existing concept is still about that concept, so it routes to UPDATE(it) and
    reaches reconcile() — never CREATE — instead of being mis-filed as new.
    """
    query = (
        "A NEW note is below, followed by EXISTING concepts, each tagged with its id. "
        "Decide whether the new note updates or contradicts one of the existing "
        "concepts -- it is about the same topic, whether it agrees with or conflicts "
        "with what that concept currently says -- or is genuinely new knowledge. A "
        "note that contradicts an existing concept still belongs to it, so choose "
        "UPDATE for it. Reply on a single line with exactly 'UPDATE <id>' (copying "
        "one of the ids above) or 'CREATE'."
    )
    blocks = [f"[{candidate.concept_id}]\n{candidate.text}" for candidate in candidates]
    context = "NEW note:\n" + draft_text + "\n\nEXISTING concepts:\n" + "\n\n".join(blocks)
    return query, context


_SELECTED_UPDATE = re.compile(
    r"\bUPDATE\b[^A-Za-z0-9]*(?P<id>[A-Za-z0-9][A-Za-z0-9/_.\-]*)", re.IGNORECASE
)


def parse_selection(
    text: str, candidate_ids: Sequence[str], name: str = "generation"
) -> Selection:
    """Parse 'UPDATE <id>' (-> SAME id) or anything else (-> CREATE) from a response.

    Mirrors the prompt-only routing parser: an UPDATE naming a candidate id is the
    only path to UPDATE; an unparseable or unknown-id answer falls to CREATE rather
    than attaching the draft to a concept the model did not clearly choose.
    """
    valid = set(candidate_ids)
    match = _SELECTED_UPDATE.search(text)
    if match is not None:
        chosen = match.group("id").strip().strip(".`")
        if chosen in valid:
            return Selection(chosen, Verdict.SAME, f"{name}: UPDATE {chosen}")
    return Selection(None, Verdict.DIFFERENT, f"{name}: {text.strip()[:60]} -> create")


def jaccard_overlap(a: str, b: str) -> float:
    set_a, set_b = set(tokenize(a)), set(tokenize(b))
    union = set_a | set_b
    if not union:
        return 1.0
    return len(set_a & set_b) / len(union)
