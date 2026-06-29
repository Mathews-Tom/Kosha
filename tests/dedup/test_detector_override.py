"""The dedup resolver's detector gate: force UPDATE on a conflict the LLM missed."""

from __future__ import annotations

from kosha.contradiction import LexicalContradictionJudge
from kosha.dedup.adjudicate import Adjudication, CandidateConcept, Selection, Verdict
from kosha.dedup.resolver import Action, resolve_draft
from kosha.extract import ConceptDraft
from kosha.index import EmbeddingIndex
from kosha.providers import LexicalEmbeddingProvider

_PROVIDER = LexicalEmbeddingProvider()
# Lands in the ambiguous band (cos ~0.76) with a numeric conflict (8 vs 64).
_CAND = "The cache holds 8 entries before eviction."
_DRAFT_CONFLICT = "The cache holds 64 entries before eviction under load."
# In the band, but a benign paraphrase: no numeric/negation cue for the detector.
_DRAFT_BENIGN = "The cache keeps a bounded number of entries before eviction overall."


class _AlwaysDifferent:
    """An adjudicator that always answers 'different concept' (the LLM miss)."""

    @property
    def name(self) -> str:
        return "always-different"

    def adjudicate(self, draft_text: str, candidate_text: str) -> Adjudication:
        return Adjudication(Verdict.DIFFERENT, "always:different")

    def select(self, draft_text: str, candidates: list[CandidateConcept]) -> Selection:
        return Selection(None, Verdict.DIFFERENT, "always:different")


def _index(*texts: str) -> tuple[EmbeddingIndex, dict[str, str]]:
    entries = {f"c{i}": _PROVIDER.embed([t])[0] for i, t in enumerate(texts)}
    concept_texts = {f"c{i}": t for i, t in enumerate(texts)}
    return EmbeddingIndex(_PROVIDER, entries), concept_texts


def _draft(body: str) -> ConceptDraft:
    return ConceptDraft(title="cache", body=body, description="", type="x", source_id="s")


def test_without_detector_a_different_verdict_creates() -> None:
    index, texts = _index(_CAND)
    decision = resolve_draft(
        _draft(_DRAFT_CONFLICT), index, texts, adjudicator=_AlwaysDifferent()
    )
    assert decision.action is Action.CREATE  # the LLM miss files it as novel


def test_detector_forces_update_on_a_numeric_conflict() -> None:
    index, texts = _index(_CAND)
    decision = resolve_draft(
        _draft(_DRAFT_CONFLICT),
        index,
        texts,
        adjudicator=_AlwaysDifferent(),
        detector=LexicalContradictionJudge(),
    )
    assert decision.action is Action.UPDATE
    assert decision.concept_id == "c0"
    assert "detector-gated conflict" in decision.rationale


def test_detector_does_not_fire_on_a_benign_paraphrase() -> None:
    index, texts = _index(_CAND)
    decision = resolve_draft(
        _draft(_DRAFT_BENIGN),
        index,
        texts,
        adjudicator=_AlwaysDifferent(),
        detector=LexicalContradictionJudge(),
    )
    # No numeric/negation cue -> the detector stays silent and the LLM's CREATE stands.
    assert decision.action is Action.CREATE
