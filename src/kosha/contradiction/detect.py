"""Contradiction detector: structured diff + judgment (system_design §4.3.1).

Detection is the first half of "detection is not enough": before the resolution
policy can act, the loop must know whether a new claim *materially* conflicts with
a prior in-force claim — asserts something that cannot also be true of the same
subject — versus merely restating or extending it.

Two stages keep the model call rare and auditable, mirroring the dedup decision:

* :func:`structured_diff` is deterministic — it measures subject overlap and
  flags the two cheap, high-precision conflict signals (a differing value on a
  shared subject; a polarity flip). It owns no judgment.
* a :class:`ContradictionJudge` makes the call. The offline
  :class:`LexicalContradictionJudge` trusts the structured signals; the
  :class:`GenerationContradictionJudge` asks a model, which is where paraphrased
  conflicts the lexical signals miss get caught (the eval's documented headroom).

:func:`find_conflict` runs the judge against a concept's in-force claims and
returns the first material conflict, with the subject-overlap score and a
rationale for the audit trail.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from kosha.model import Claim
from kosha.providers.base import GenerationProvider
from kosha.providers.tokens import tokenize

# Negation / polarity cues that survive lexical tokenization (alnum runs only).
_NEGATION_CUES = frozenset(
    {
        "not",
        "no",
        "never",
        "cannot",
        "without",
        "prohibited",
        "disallowed",
        "forbidden",
        "ineligible",
        "excluded",
        "unavailable",
    }
)
_NUMBER = re.compile(r"\d+")


class ContradictionVerdict(StrEnum):
    """Whether a new claim materially conflicts with a prior one."""

    CONFLICT = "conflict"
    NONE = "none"


@dataclass(frozen=True)
class DiffSignal:
    """Deterministic structured-diff signals between a prior and a new claim."""

    subject_overlap: float
    identical: bool
    numeric_conflict: bool
    negation_conflict: bool


@dataclass(frozen=True)
class Judgment:
    """A judge's verdict plus the rationale recorded for the audit log."""

    verdict: ContradictionVerdict
    rationale: str


@dataclass(frozen=True)
class ConflictReport:
    """The detector's outcome for a new claim against one concept's claims."""

    verdict: ContradictionVerdict
    old_claim_id: str | None
    new_statement: str
    score: float
    rationale: str

    @property
    def conflicting(self) -> bool:
        """Whether a material conflict was found."""
        return self.verdict is ContradictionVerdict.CONFLICT


def structured_diff(old: str, new: str) -> DiffSignal:
    """Measure subject overlap and the cheap conflict signals between two claims."""
    overlap = _jaccard(old, new)
    identical = old.strip() == new.strip()
    old_numbers, new_numbers = _numbers(old), _numbers(new)
    numeric_conflict = bool(old_numbers) and bool(new_numbers) and old_numbers != new_numbers
    negation_conflict = _has_negation(old) != _has_negation(new)
    return DiffSignal(overlap, identical, numeric_conflict, negation_conflict)


class ContradictionJudge(Protocol):
    """Judges whether a new claim materially conflicts with a prior claim."""

    @property
    def name(self) -> str:
        """Stable identifier recorded in the audit log / eval report."""
        ...

    def judge(self, old: str, new: str, signal: DiffSignal) -> Judgment:
        """Return a conflict verdict for the prior/new claim pair."""
        ...


class LexicalContradictionJudge:
    """Deterministic offline judge: trust the structured-diff signals.

    A material conflict is a differing value or a polarity flip on a *shared*
    subject; an identical statement is a restatement, and low subject overlap is
    an unrelated addition. Paraphrased conflicts that carry neither a numeric nor
    a negation signal slip past it — the headroom a real model closes.
    """

    def __init__(self, overlap_min: float = 0.4) -> None:
        if not 0.0 <= overlap_min <= 1.0:
            raise ValueError("overlap_min must be in [0, 1]")
        self._overlap_min = overlap_min

    @property
    def name(self) -> str:
        return f"lexical-overlap-{self._overlap_min:.2f}"

    def judge(self, old: str, new: str, signal: DiffSignal) -> Judgment:
        if signal.identical:
            return Judgment(ContradictionVerdict.NONE, "identical restatement")
        if signal.subject_overlap < self._overlap_min:
            return Judgment(
                ContradictionVerdict.NONE,
                f"subject overlap {signal.subject_overlap:.3f} < {self._overlap_min:.2f}",
            )
        if signal.numeric_conflict:
            return Judgment(
                ContradictionVerdict.CONFLICT,
                f"differing value on shared subject (overlap {signal.subject_overlap:.3f})",
            )
        if signal.negation_conflict:
            return Judgment(
                ContradictionVerdict.CONFLICT,
                f"polarity flip on shared subject (overlap {signal.subject_overlap:.3f})",
            )
        return Judgment(
            ContradictionVerdict.NONE,
            "shared subject, no value or polarity divergence "
            f"(overlap {signal.subject_overlap:.3f})",
        )


class GenerationContradictionJudge:
    """Real LLM judge: prompt a generation provider and parse the verdict."""

    def __init__(self, provider: GenerationProvider) -> None:
        self._provider = provider

    @property
    def name(self) -> str:
        return f"generation:{self._provider.name}"

    def judge(self, old: str, new: str, signal: DiffSignal) -> Judgment:
        query, context = build_contradiction_prompt(old, new)
        generation = self._provider.generate(query, context)
        verdict = parse_verdict(generation.text)
        return Judgment(verdict, f"{self.name}: {generation.text.strip()}")


class DetectorGatedJudge:
    """Code-owned detectors gating an LLM judge (spike S2, Track C).

    The deterministic structured-diff signals are authoritative: when they flag a
    material conflict (a differing value or a polarity flip on a shared subject)
    the verdict is CONFLICT *without* an LLM call, so a conflict the model would
    miss still forces :func:`~kosha.contradiction.escalate.reconcile`. A clearly
    unrelated pair (subject overlap below the threshold) or an identical
    restatement is settled NONE, also without an LLM call. Only the ambiguous
    residue — a shared subject with no value or polarity cue (unit, partial,
    paraphrase) — is deferred to the wrapped LLM judge. The prompt-only baseline
    has no such gate; that asymmetry is the loop's structural edge Gate-0 v2
    measures, and it bounds the LLM to at most one call per claim comparison.
    """

    def __init__(self, llm: ContradictionJudge, *, overlap_min: float = 0.4) -> None:
        if not 0.0 <= overlap_min <= 1.0:
            raise ValueError("overlap_min must be in [0, 1]")
        self._llm = llm
        self._overlap_min = overlap_min
        self._detector = LexicalContradictionJudge(overlap_min)

    @property
    def name(self) -> str:
        return f"detector-gated({self._llm.name})"

    def judge(self, old: str, new: str, signal: DiffSignal) -> Judgment:
        detected = self._detector.judge(old, new, signal)
        if detected.verdict is ContradictionVerdict.CONFLICT:
            return Judgment(detected.verdict, f"detector forced: {detected.rationale}")
        if signal.identical or signal.subject_overlap < self._overlap_min:
            return detected  # restatement or unrelated: settled without an LLM call
        return self._llm.judge(old, new, signal)


def detect_conflict(
    old_claim: Claim, new_statement: str, *, judge: ContradictionJudge
) -> ConflictReport:
    """Judge whether ``new_statement`` conflicts with a single ``old_claim``."""
    signal = structured_diff(old_claim.statement, new_statement)
    judgment = judge.judge(old_claim.statement, new_statement, signal)
    return ConflictReport(
        verdict=judgment.verdict,
        old_claim_id=old_claim.claim_id,
        new_statement=new_statement,
        score=signal.subject_overlap,
        rationale=judgment.rationale,
    )


def find_conflict(
    claims: Sequence[Claim], new_statement: str, *, judge: ContradictionJudge
) -> ConflictReport:
    """Return the first material conflict ``new_statement`` has with ``claims``.

    Claims are checked in descending subject overlap so the most-likely subject
    match is judged first; the first CONFLICT wins. With no conflict, the
    top-overlap report is returned (NONE) so the audit trail still records what
    the new claim was closest to.
    """
    ranked = sorted(
        claims,
        key=lambda claim: (
            -structured_diff(claim.statement, new_statement).subject_overlap,
            claim.claim_id,
        ),
    )
    fallback: ConflictReport | None = None
    for claim in ranked:
        report = detect_conflict(claim, new_statement, judge=judge)
        if report.conflicting:
            return report
        if fallback is None:
            fallback = report
    if fallback is not None:
        return fallback
    return ConflictReport(
        verdict=ContradictionVerdict.NONE,
        old_claim_id=None,
        new_statement=new_statement,
        score=0.0,
        rationale="no in-force claim to compare against",
    )


def build_contradiction_prompt(old: str, new: str) -> tuple[str, str]:
    """Return the (query, context) pair posed to the generation provider."""
    query = (
        "Decide whether the new claim materially contradicts the prior claim — "
        "asserts something that cannot also be true of the same subject — or is "
        "compatible (a restatement, a refinement, or an unrelated addition). "
        "Answer with exactly one word: conflict or compatible."
    )
    context = f"Prior claim:\n{old}\n\nNew claim:\n{new}"
    return query, context


def parse_verdict(text: str) -> ContradictionVerdict:
    """Parse a conflict verdict from a provider response (compatible wins ties)."""
    lowered = text.strip().lower()
    no_conflict_cues = ("no conflict", "not a conflict", "compatible", "consistent")
    conflict_cues = ("conflict", "contradict", "incompatible", "mutually exclusive")
    if any(cue in lowered for cue in no_conflict_cues):
        return ContradictionVerdict.NONE
    if any(cue in lowered for cue in conflict_cues):
        return ContradictionVerdict.CONFLICT
    if "none" in lowered:
        return ContradictionVerdict.NONE
    raise ValueError(f"no contradiction verdict keyword in response: {text!r}")


def _numbers(text: str) -> frozenset[str]:
    return frozenset(_NUMBER.findall(text))


def _has_negation(text: str) -> bool:
    return bool(_NEGATION_CUES.intersection(tokenize(text)))


def _jaccard(a: str, b: str) -> float:
    set_a, set_b = set(tokenize(a)), set(tokenize(b))
    union = set_a | set_b
    if not union:
        return 1.0
    return len(set_a & set_b) / len(union)
