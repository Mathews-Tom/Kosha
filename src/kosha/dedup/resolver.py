"""Resolve a concept draft to a dedup Decision (system_design §4.3).

The resolver wires the deterministic steps to the single LLM surface: find
nearest candidates (M6 PR-1), route by two thresholds (M6 PR-2), and reach an
:class:`~kosha.dedup.adjudicate.Adjudicator` only for the ambiguous band. A SPLIT
verdict triggers a granularity split + re-resolve (M6 PR-4): the draft is
re-segmented and each piece re-resolved into child decisions. Every decision
carries the score and a rationale that compose the
audit log (overview §6).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from kosha.dedup.adjudicate import Adjudicator, CandidateConcept, Verdict
from kosha.dedup.candidates import draft_query_text, nearest_candidates
from kosha.dedup.decision import (
    DEFAULT_THRESHOLDS,
    Action,
    Route,
    Thresholds,
    route_candidates,
)
from kosha.dedup.split import Splitter
from kosha.extract import ConceptDraft
from kosha.index.embedding import EmbeddingIndex, Neighbor

if TYPE_CHECKING:
    from kosha.contradiction.detect import ContradictionJudge


@dataclass(frozen=True)
class Decision:
    """The terminal dedup decision for a draft, with its audit trail.

    ``concept_id`` is the UPDATE target (``None`` for CREATE/SPLIT). ``score`` is
    the top nearest-neighbor cosine; ``adjudicated`` records whether the LLM band
    was reached. ``parts`` holds the re-resolved child decisions of a SPLIT.
    """

    action: Action
    concept_id: str | None
    score: float
    rationale: str
    adjudicated: bool = False
    parts: tuple[Decision, ...] = ()


def resolve_draft(
    draft: ConceptDraft,
    index: EmbeddingIndex,
    concept_texts: Mapping[str, str],
    *,
    adjudicator: Adjudicator,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
    k: int = 5,
    splitter: Splitter | None = None,
    detector: ContradictionJudge | None = None,
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
    # Ambiguous band: the reserved LLM call. With a single neighbor the question
    # is "is this the same as that one?" (adjudicate); with several it is "which
    # of these, if any?" (select over the top-k).
    assert routing.candidate is not None  # ADJUDICATE implies a top candidate
    draft_text = draft_query_text(draft)
    candidate_concepts = [
        CandidateConcept(neighbor.concept_id, concept_texts.get(neighbor.concept_id, ""))
        for neighbor in candidates
    ]
    verdict: Verdict
    target_id: str | None
    detail: str
    if len(candidate_concepts) == 1:
        adjudication = adjudicator.adjudicate(draft_text, candidate_concepts[0].text)
        verdict = adjudication.verdict
        target_id = routing.candidate.concept_id
        detail = adjudication.rationale
    else:
        selection = adjudicator.select(draft_text, candidate_concepts)
        verdict = selection.verdict
        target_id = selection.concept_id
        detail = selection.rationale
    rationale = f"{routing.rationale}; {detail}"
    if verdict is Verdict.SAME:
        assert target_id is not None  # SAME implies a chosen concept
        return Decision(Action.UPDATE, target_id, routing.score, rationale, adjudicated=True)
    if verdict is Verdict.DIFFERENT:
        gated = _detector_override(detector, draft_text, routing.candidate, concept_texts)
        if gated is not None:
            return Decision(
                Action.UPDATE, gated[0], routing.score, f"{rationale}; {gated[1]}", adjudicated=True
            )
        return Decision(Action.CREATE, None, routing.score, rationale, adjudicated=True)
    if splitter is None:
        return Decision(Action.SPLIT, None, routing.score, rationale, adjudicated=True)
    parts = tuple(
        resolve_draft(
            sub_draft,
            index,
            concept_texts,
            adjudicator=adjudicator,
            thresholds=thresholds,
            k=k,
            splitter=None,
            detector=detector,
        )
        for sub_draft in splitter(draft)
    )
    return Decision(
        Action.SPLIT, None, routing.score, rationale, adjudicated=True, parts=parts
    )


def _detector_override(
    detector: ContradictionJudge | None,
    draft_text: str,
    candidate: Neighbor | None,
    concept_texts: Mapping[str, str],
) -> tuple[str, str] | None:
    """Force UPDATE when a code-owned detector flags a conflict the LLM called DIFFERENT.

    The adjudicator answered "different concept", but a deterministic structured-
    diff conflict against the nearest concept means the draft *contradicts* it
    rather than being novel — route it to that concept so the conflict reaches
    reconcile() instead of being filed as a new concept. Off by default; only the
    gated loop path passes a detector, so existing routing is unchanged.
    """
    if detector is None or candidate is None:
        return None
    # Local import: dedup is imported during kosha.contradiction init, so a
    # module-level contradiction import here would close an import cycle.
    from kosha.contradiction.detect import ContradictionVerdict, structured_diff

    prior = concept_texts.get(candidate.concept_id, "")
    if not prior:
        return None
    judgment = detector.judge(prior, draft_text, structured_diff(prior, draft_text))
    if judgment.verdict is ContradictionVerdict.CONFLICT:
        return candidate.concept_id, f"detector-gated conflict: {judgment.rationale}"
    return None
