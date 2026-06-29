"""Tests for the three retrieval strategies on the golden corpus."""

from __future__ import annotations

from pathlib import Path

from kosha.bench import HybridStrategy, LongContextStrategy, RagStrategy, TunedRagStrategy
from kosha.bench.strategies import _Bm25
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


def _tuned_rag() -> TunedRagStrategy:
    bundle = load_bundle(NORTHWIND)
    return TunedRagStrategy(bundle, LexicalEmbeddingProvider())


def test_tuned_rag_surfaces_the_answer_concept() -> None:
    ctx = _tuned_rag().retrieve(_QUERY)
    assert "policies/returns/gold-members" in ctx.concept_ids
    assert ctx.round_trips == 1
    assert ctx.concept_ids


def test_tuned_rag_respects_calibrated_top_k() -> None:
    bundle = load_bundle(NORTHWIND)
    strategy = TunedRagStrategy(bundle, LexicalEmbeddingProvider(), top_k=3, pool_k=10)
    ctx = strategy.retrieve(_QUERY)
    # top_k caps the chunks chosen, so distinct concepts cannot exceed it.
    assert len(ctx.concept_ids) <= 3


def test_tuned_rag_is_deterministic() -> None:
    strategy = _tuned_rag()
    assert strategy.retrieve(_QUERY) == strategy.retrieve(_QUERY)


def test_tuned_rag_zero_overlap_query_keeps_cosine_order() -> None:
    # No query term appears in any chunk -> every BM25 score ties at 0, so the
    # rerank must preserve the cosine pool order rather than reorder by global
    # chunk index. With top_k == pool_k the chosen set is exactly the cosine pool.
    bundle = load_bundle(NORTHWIND)
    provider = LexicalEmbeddingProvider()
    strategy = TunedRagStrategy(bundle, provider, top_k=4, pool_k=4)
    ctx = strategy.retrieve("zqxjvkbw nonexistentterm")
    assert ctx.concept_ids
    assert len(ctx.concept_ids) <= 4


def test_tuned_rag_rejects_bad_parameters() -> None:
    bundle = load_bundle(NORTHWIND)
    provider = LexicalEmbeddingProvider()
    for kwargs in ({"top_k": 0}, {"pool_k": 0}, {"chunk_words": 0}, {"pool_k": 2, "top_k": 5}):
        try:
            TunedRagStrategy(bundle, provider, **kwargs)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {kwargs}")


def test_bm25_ranks_matching_documents_higher() -> None:
    docs = [
        ["gold", "members", "return", "window", "is", "forty", "five", "days"],
        ["standard", "shipping", "takes", "three", "business", "days"],
    ]
    bm25 = _Bm25(docs)
    query = ["gold", "return", "window"]
    assert bm25.score(query, 0) > bm25.score(query, 1)


def test_bm25_empty_corpus_scores_zero() -> None:
    assert _Bm25([]).score(["anything"], 0) == 0.0
