"""Tests for the concept embedding index against the golden corpus."""

from __future__ import annotations

from pathlib import Path

import pytest

from kosha.index import EmbeddingIndex
from kosha.okf import load_bundle
from kosha.providers import LexicalEmbeddingProvider

NORTHWIND = Path(__file__).resolve().parents[2] / "bundles" / "northwind"


def _build() -> EmbeddingIndex:
    bundle = load_bundle(NORTHWIND)
    return EmbeddingIndex.build(bundle, LexicalEmbeddingProvider())


def test_index_covers_every_concept() -> None:
    index = _build()
    assert len(index) == 12
    assert "policies/returns/gold-members" in index.concept_ids


def test_query_surfaces_the_relevant_concept() -> None:
    index = _build()
    hits = [n.concept_id for n in index.query_text("gold member 45 day return window", k=3)]
    assert "policies/returns/gold-members" in hits


def test_query_results_are_ranked_descending_and_deterministic() -> None:
    index = _build()
    first = index.query_text("how are refunds processed", k=5)
    second = index.query_text("how are refunds processed", k=5)
    assert first == second
    scores = [n.score for n in first]
    assert scores == sorted(scores, reverse=True)
    assert "policies/refunds" in {n.concept_id for n in first}


def test_query_rejects_non_positive_k() -> None:
    with pytest.raises(ValueError, match="k must be positive"):
        _build().query_text("anything", k=0)


def test_save_load_round_trip_preserves_queries(tmp_path: Path) -> None:
    index = _build()
    path = tmp_path / "index.json"
    index.save(path)
    reloaded = EmbeddingIndex.load(path, LexicalEmbeddingProvider())
    assert reloaded.query_text("standard return window", k=3) == index.query_text(
        "standard return window", k=3
    )


def test_load_rejects_a_mismatched_provider(tmp_path: Path) -> None:
    bundle = load_bundle(NORTHWIND)
    index = EmbeddingIndex.build(bundle, LexicalEmbeddingProvider(dimension=64))
    path = tmp_path / "index.json"
    index.save(path)
    with pytest.raises(ValueError, match="provider"):
        EmbeddingIndex.load(path, LexicalEmbeddingProvider(dimension=128))
