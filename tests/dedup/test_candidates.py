"""Tests for nearest-neighbor candidate lookup over the golden corpus."""

from __future__ import annotations

from pathlib import Path

import pytest

from kosha.dedup import draft_query_text, nearest_candidates
from kosha.extract import ConceptDraft
from kosha.index import EmbeddingIndex
from kosha.index.embedding import index_text
from kosha.model import Concept
from kosha.okf import load_bundle
from kosha.providers import LexicalEmbeddingProvider

NORTHWIND = Path(__file__).resolve().parents[2] / "bundles" / "northwind"


def _build_index() -> EmbeddingIndex:
    return EmbeddingIndex.build(load_bundle(NORTHWIND), LexicalEmbeddingProvider())


def _draft_from(concept: Concept) -> ConceptDraft:
    return ConceptDraft(
        title=concept.frontmatter.title or concept.concept_id,
        body=concept.body,
        description=concept.frontmatter.description or "",
        type=concept.frontmatter.type,
        source_id="reingest://northwind",
    )


def test_draft_query_text_mirrors_index_text() -> None:
    # The self-match guarantee: a draft built from a concept embeds identically
    # to that concept's index entry, so a repeated ingest scores cosine 1.0.
    concept = load_bundle(NORTHWIND).concepts["policies/returns/gold-members"]
    assert draft_query_text(_draft_from(concept)) == index_text(concept)


def test_reingested_concept_self_matches_at_top() -> None:
    bundle = load_bundle(NORTHWIND)
    index = EmbeddingIndex.build(bundle, LexicalEmbeddingProvider())
    for concept_id, concept in bundle.concepts.items():
        top = nearest_candidates(_draft_from(concept), index, k=1)[0]
        assert top.concept_id == concept_id
        assert top.score == pytest.approx(1.0)


def test_candidates_are_ranked_descending() -> None:
    index = _build_index()
    draft = ConceptDraft(
        title="Gold returns",
        body="Gold members get a 45 day window to return an item.",
        description="Gold tier return window.",
        type="Policy",
        source_id="s://1",
    )
    candidates = nearest_candidates(draft, index, k=5)
    assert "policies/returns/gold-members" in {c.concept_id for c in candidates}
    scores = [c.score for c in candidates]
    assert scores == sorted(scores, reverse=True)


def test_k_limits_the_number_of_candidates() -> None:
    index = _build_index()
    draft = ConceptDraft(
        title="x", body="refund window", description="refunds", type="Policy", source_id="s"
    )
    assert len(nearest_candidates(draft, index, k=3)) == 3


def test_empty_index_yields_no_candidates() -> None:
    index = EmbeddingIndex(LexicalEmbeddingProvider(), {})
    draft = ConceptDraft(
        title="x", body="anything", description="d", type="t", source_id="s"
    )
    assert nearest_candidates(draft, index) == []


def test_non_positive_k_is_rejected() -> None:
    index = _build_index()
    draft = ConceptDraft(
        title="x", body="b", description="d", type="t", source_id="s"
    )
    with pytest.raises(ValueError, match="k must be positive"):
        nearest_candidates(draft, index, k=0)
