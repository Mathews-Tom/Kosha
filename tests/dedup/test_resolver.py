"""Tests for the dedup resolver: routing + reserved-band adjudication."""

from __future__ import annotations

import pytest

from kosha.dedup.adjudicate import Adjudication, Verdict
from kosha.dedup.resolver import Action, resolve_draft
from kosha.extract import ConceptDraft
from kosha.index import EmbeddingIndex
from kosha.providers import LexicalEmbeddingProvider

_PROVIDER = LexicalEmbeddingProvider()

# A lexical paraphrase pair that lands in the ambiguous band (cosine ~0.25).
_CAND_BAND = "Standard shipping takes 3-5 business days."
_DRAFT_BAND = "Delivery normally arrives in three to five business days."


class _FixedAdjudicator:
    """Returns a preset verdict; records whether it was consulted."""

    def __init__(self, verdict: Verdict) -> None:
        self._verdict = verdict
        self.calls = 0

    @property
    def name(self) -> str:
        return "fixed"

    def adjudicate(self, draft_text: str, candidate_text: str) -> Adjudication:
        self.calls += 1
        return Adjudication(self._verdict, f"fixed:{self._verdict.value}")


class _ForbiddenAdjudicator:
    """Fails if the resolver reaches it on a clear-cut score."""

    @property
    def name(self) -> str:
        return "forbidden"

    def adjudicate(self, draft_text: str, candidate_text: str) -> Adjudication:
        raise AssertionError("adjudicator must not be called outside the ambiguous band")


def _index(*texts: str) -> tuple[EmbeddingIndex, dict[str, str]]:
    entries = {f"c{i}": _PROVIDER.embed([t])[0] for i, t in enumerate(texts)}
    concept_texts = {f"c{i}": t for i, t in enumerate(texts)}
    return EmbeddingIndex(_PROVIDER, entries), concept_texts


def _draft(body: str) -> ConceptDraft:
    return ConceptDraft(title="t", body=body, description="", type="x", source_id="s")


def test_clear_match_updates_without_calling_the_llm() -> None:
    text = "Gold members may return an item within 45 days of delivery."
    index, texts = _index(text)
    decision = resolve_draft(
        _draft(text), index, texts, adjudicator=_ForbiddenAdjudicator()
    )
    assert decision.action is Action.UPDATE
    assert decision.concept_id == "c0"
    assert decision.score == pytest.approx(1.0)
    assert decision.adjudicated is False


def test_clear_novelty_creates_without_calling_the_llm() -> None:
    index, texts = _index("Refunds post to the original card after approval.")
    decision = resolve_draft(
        _draft("Membership tiers grant escalating loyalty perks."),
        index,
        texts,
        adjudicator=_ForbiddenAdjudicator(),
    )
    assert decision.action is Action.CREATE
    assert decision.concept_id is None
    assert decision.adjudicated is False


def test_ambiguous_same_verdict_updates() -> None:
    index, texts = _index(_CAND_BAND)
    adjudicator = _FixedAdjudicator(Verdict.SAME)
    decision = resolve_draft(_draft(_DRAFT_BAND), index, texts, adjudicator=adjudicator)
    assert decision.action is Action.UPDATE
    assert decision.concept_id == "c0"
    assert decision.adjudicated is True
    assert adjudicator.calls == 1
    assert "adjudicate" in decision.rationale and "fixed:same" in decision.rationale


def test_ambiguous_different_verdict_creates() -> None:
    index, texts = _index(_CAND_BAND)
    decision = resolve_draft(
        _draft(_DRAFT_BAND), index, texts, adjudicator=_FixedAdjudicator(Verdict.DIFFERENT)
    )
    assert decision.action is Action.CREATE
    assert decision.adjudicated is True


def test_ambiguous_split_verdict_yields_a_split_leaf() -> None:
    index, texts = _index(_CAND_BAND)
    decision = resolve_draft(
        _draft(_DRAFT_BAND), index, texts, adjudicator=_FixedAdjudicator(Verdict.SPLIT)
    )
    assert decision.action is Action.SPLIT
    assert decision.adjudicated is True


def test_empty_index_creates() -> None:
    index = EmbeddingIndex(_PROVIDER, {})
    decision = resolve_draft(
        _draft("anything at all"), index, {}, adjudicator=_ForbiddenAdjudicator()
    )
    assert decision.action is Action.CREATE
