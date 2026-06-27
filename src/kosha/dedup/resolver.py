"""Resolve a concept draft to a dedup Decision (system_design §4.3).

The resolver wires the deterministic steps to the single LLM surface: find
nearest candidates (M6 PR-1), route by two thresholds (M6 PR-2), and reach an
:class:`~kosha.dedup.adjudicate.Adjudicator` only for the ambiguous band. A SPLIT
verdict is recorded as a leaf here; the granularity split + re-resolve is added
in M6 PR-4. Every decision carries the score and a rationale that compose the
audit log (overview §6).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from kosha.dedup.adjudicate import Adjudicator, Verdict
from kosha.dedup.candidates import draft_query_text, nearest_candidates
from kosha.dedup.decision import (
    DEFAULT_THRESHOLDS,
    Action,
    Route,
    Thresholds,
    route_candidates,
)
from kosha.extract import ConceptDraft
from kosha.index.embedding import EmbeddingIndex


@dataclass(frozen=True)
class Decision:
    """The terminal dedup decision for a draft, with its audit trail.

    ``concept_id`` is the UPDATE target (``None`` for CREATE/SPLIT). ``score`` is
    the top nearest-neighbor cosine; ``adjudicated`` records whether the LLM band
    was reached.
    """

    action: Action
    concept_id: str | None
    score: float
    rationale: str
    adjudicated: bool = False


def resolve_draft(
    draft: ConceptDraft,
    index: EmbeddingIndex,
    concept_texts: Mapping[str, str],
    *,
    adjudicator: Adjudicator,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
    k: int = 5,
) -> Decision:
    """Resolve ``draft`` to UPDATE / CREATE / SPLIT against ``index``.

    ``concept_texts`` maps a concept_id to the text it was indexed as; the
    adjudicator needs the candidate's text to judge the ambiguous band.
    """
    candidates = nearest_candidates(draft, index, k)
    routing = route_candidates(candidates, thresholds)
    if routing.route is Route.UPDATE:
        assert routing.candidate is not None  # UPDATE implies a top candidate
        return Decision(
            Action.UPDATE, routing.candidate.concept_id, routing.score, routing.rationale
        )
    if routing.route is Route.CREATE:
        return Decision(Action.CREATE, None, routing.score, routing.rationale)
    # Ambiguous band: the single reserved LLM call.
    assert routing.candidate is not None  # ADJUDICATE implies a top candidate
    candidate_id = routing.candidate.concept_id
    adjudication = adjudicator.adjudicate(
        draft_query_text(draft), concept_texts.get(candidate_id, "")
    )
    rationale = f"{routing.rationale}; {adjudication.rationale}"
    if adjudication.verdict is Verdict.SAME:
        return Decision(Action.UPDATE, candidate_id, routing.score, rationale, adjudicated=True)
    if adjudication.verdict is Verdict.DIFFERENT:
        return Decision(Action.CREATE, None, routing.score, rationale, adjudicated=True)
    return Decision(Action.SPLIT, None, routing.score, rationale, adjudicated=True)
