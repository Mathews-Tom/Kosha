"""Tests for the three retrieval strategies on the golden corpus."""

from __future__ import annotations

from pathlib import Path

from kosha.bench import HybridStrategy, LongContextStrategy, RagStrategy
from kosha.index import EmbeddingIndex
from kosha.okf import load_bundle
from kosha.providers import LexicalEmbeddingProvider, count_tokens

NORTHWIND = Path(__file__).resolve().parents[2] / "bundles" / "northwind"
_QUERY = "how long does a gold member have to return an item"


def _fixtures() -> tuple[HybridStrategy, RagStrategy, LongContextStrategy]:
    bundle = load_bundle(NORTHWIND)
    provider = LexicalEmbeddingProvider()
    index = EmbeddingIndex.build(bundle, provider)
    return (
        HybridStrategy(bundle, index),
        RagStrategy(bundle, provider),
        LongContextStrategy(bundle),
    )


def test_hybrid_surfaces_the_answer_concept_with_a_minimal_set() -> None:
    hybrid, _, _ = _fixtures()
    ctx = hybrid.retrieve(_QUERY)
    assert "policies/returns/gold-members" in ctx.concept_ids
    assert len(ctx.concept_ids) <= 6
    assert ctx.round_trips == 1


def test_long_context_loads_the_whole_corpus_without_retrieval() -> None:
    _, _, long_context = _fixtures()
    ctx = long_context.retrieve(_QUERY)
    assert len(ctx.concept_ids) == 12
    assert ctx.round_trips == 0


def test_rag_returns_top_k_chunk_sources() -> None:
    _, rag, _ = _fixtures()
    ctx = rag.retrieve(_QUERY)
    assert ctx.round_trips == 1
    assert ctx.concept_ids
    assert len(ctx.concept_ids) <= 5


def test_hybrid_context_is_smaller_than_long_context() -> None:
    hybrid, rag, long_context = _fixtures()
    hybrid_tokens = count_tokens(hybrid.retrieve(_QUERY).text)
    rag_tokens = count_tokens(rag.retrieve(_QUERY).text)
    long_tokens = count_tokens(long_context.retrieve(_QUERY).text)
    assert hybrid_tokens < long_tokens
    assert rag_tokens < long_tokens


def test_strategies_are_deterministic() -> None:
    hybrid, rag, long_context = _fixtures()
    for strategy in (hybrid, rag, long_context):
        assert strategy.retrieve(_QUERY) == strategy.retrieve(_QUERY)
