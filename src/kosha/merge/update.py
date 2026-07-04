"""UPDATE path: claim-targeted body merge (M7 PR-3).

An UPDATE does not rewrite the concept body. It segments the incoming draft into
candidate statements and, for each, asks a *claim targeter* which in-force claim
the statement revises:

* a hit supersedes exactly that claim (old ``superseded``, new ``current``); and
* a miss appends a new claim to the concept.

The body is then re-projected from the claims, so only the targeted claims change
and every unrelated claim's rendered text is left byte-identical — the fidelity
property the §7.1 edit-drift guard requires. Targeting is the milestone's single
LLM surface (eval-gated): the deterministic :class:`LexicalClaimTargeter` keeps
the pipeline offline and reproducible, while :class:`GenerationClaimTargeter`
routes the judgment to a provider where one is configured.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from kosha.extract import ConceptDraft
from kosha.merge.claims import current_claims, make_claim, render_body, supersede_claim
from kosha.merge.create import segment_statements, source_citation
from kosha.model import Claim, Concept, Source
from kosha.providers.base import GenerationProvider
from kosha.providers.tokens import tokenize

_NONE = "none"


class ClaimTargeter(Protocol):
    """Decides which in-force claim an incoming statement revises, if any."""

    @property
    def name(self) -> str:
        """Stable identifier recorded in eval reports."""
        ...

    def target(self, statement: str, candidates: Sequence[Claim]) -> str | None:
        """Return the ``claim_id`` ``statement`` revises, or ``None`` if novel."""
        ...


class LexicalClaimTargeter:
    """Deterministic targeter: highest Jaccard overlap above a threshold wins."""

    def __init__(self, threshold: float = 0.3) -> None:
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be in [0, 1]")
        self._threshold = threshold

    @property
    def name(self) -> str:
        return f"lexical-jaccard-{self._threshold:.2f}"

    def target(self, statement: str, candidates: Sequence[Claim]) -> str | None:
        best_id: str | None = None
        best_score = self._threshold
        for candidate in candidates:
            score = jaccard_overlap(statement, candidate.statement)
            if score >= best_score:
                best_score = score
                best_id = candidate.claim_id
        return best_id


class GenerationClaimTargeter:
    """LLM targeter: prompt a generation provider and parse the chosen claim."""

    def __init__(self, provider: GenerationProvider) -> None:
        self._provider = provider

    @property
    def name(self) -> str:
        return f"generation:{self._provider.name}"

    def target(self, statement: str, candidates: Sequence[Claim]) -> str | None:
        if not candidates:
            return None
        query, context = build_targeting_prompt(statement, candidates)
        generation = self._provider.generate(query, context)
        return parse_target(generation.text, candidates)


def build_targeting_prompt(statement: str, candidates: Sequence[Claim]) -> tuple[str, str]:
    """Return the (query, context) pair posed to the generation provider."""
    lines = [f"{i}. {claim.statement}" for i, claim in enumerate(candidates, start=1)]
    context = "Existing claims:\n" + "\n".join(lines)
    query = (
        f"New statement: {statement}\n"
        "Reply with the number of the existing claim it revises, or NONE if it is new."
    )
    return query, context


def parse_target(text: str, candidates: Sequence[Claim]) -> str | None:
    """Parse a 1-based claim number (or NONE) from a provider response."""
    lowered = text.strip().lower()
    if _NONE in lowered:
        return None
    for token in lowered.replace(".", " ").split():
        if token.isdigit():
            index = int(token)
            if 1 <= index <= len(candidates):
                return candidates[index - 1].claim_id
    return None


def merge_update(
    concept: Concept,
    draft: ConceptDraft,
    source: Source,
    asserted_at: datetime,
    *,
    targeter: ClaimTargeter,
) -> Concept:
    """Merge ``draft`` into ``concept`` by superseding the claims it revises.

    Re-asserting a claim verbatim is a no-op (no churn); any genuine supersede or
    new claim bumps the concept ``timestamp``. Returns a new concept; the input
    is left untouched.
    """
    citation = source_citation(source)
    claims: list[Claim] = list(concept.claims)
    changed = False
    for statement in segment_statements(draft.body) or [draft.description]:
        target_id = targeter.target(statement, current_claims(claims))
        if target_id is None:
            claims.append(
                make_claim(statement, source.source_id, asserted_at, citations=[citation])
            )
            changed = True
        elif _claim(claims, target_id).statement != statement:
            claims, _ = supersede_claim(
                claims,
                target_id,
                statement=statement,
                source_id=source.source_id,
                asserted_at=asserted_at,
                citations=[citation],
            )
            changed = True
    if not changed:
        return concept
    frontmatter = concept.frontmatter.model_copy(update={"timestamp": asserted_at})
    return concept.model_copy(
        update={"claims": claims, "body": render_body(claims), "frontmatter": frontmatter}
    )


def _claim(claims: Sequence[Claim], claim_id: str) -> Claim:
    for claim in claims:
        if claim.claim_id == claim_id:
            return claim
    raise KeyError(f"no claim {claim_id!r} in concept")


def jaccard_overlap(a: str, b: str) -> float:
    set_a, set_b = set(tokenize(a)), set(tokenize(b))
    union = set_a | set_b
    if not union:
        return 0.0
    return len(set_a & set_b) / len(union)
