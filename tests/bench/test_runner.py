"""Tests for the benchmark runner and table rendering."""

from __future__ import annotations

from pathlib import Path

import pytest

from kosha.bench import (
    STRATEGY_ORDER,
    render_table,
    run_benchmark,
)
from kosha.bench.runner import StrategyResult
from kosha.okf import load_bundle
from kosha.providers import ExtractiveGenerationProvider, LexicalEmbeddingProvider

NORTHWIND = Path(__file__).resolve().parents[2] / "bundles" / "northwind"


def _run() -> tuple[StrategyResult, StrategyResult, StrategyResult]:
    bundle = load_bundle(NORTHWIND)
    report = run_benchmark(
        bundle, LexicalEmbeddingProvider(), ExtractiveGenerationProvider()
    )
    return (
        report.by_name("hybrid"),
        report.by_name("rag"),
        report.by_name("long_context"),
    )


def test_report_has_all_three_strategies_in_order() -> None:
    bundle = load_bundle(NORTHWIND)
    report = run_benchmark(
        bundle, LexicalEmbeddingProvider(), ExtractiveGenerationProvider()
    )
    assert tuple(r.name for r in report.results) == STRATEGY_ORDER
    assert report.query_count == 8


def test_token_and_quality_metrics_are_deterministic() -> None:
    first = [_strip_latency(r) for r in _run()]
    second = [_strip_latency(r) for r in _run()]
    assert first == second


def test_hybrid_answers_every_query_with_fewer_tokens_than_long_context() -> None:
    hybrid, _, long_context = _run()
    assert hybrid.concept_recall == 1.0
    assert hybrid.avg_context_tokens < long_context.avg_context_tokens


def test_render_table_lists_every_strategy() -> None:
    bundle = load_bundle(NORTHWIND)
    report = run_benchmark(
        bundle, LexicalEmbeddingProvider(), ExtractiveGenerationProvider()
    )
    table = render_table(report)
    for name in STRATEGY_ORDER:
        assert name in table
    assert "Concept recall" in table


def test_by_name_rejects_unknown_strategy() -> None:
    bundle = load_bundle(NORTHWIND)
    report = run_benchmark(
        bundle, LexicalEmbeddingProvider(), ExtractiveGenerationProvider()
    )
    with pytest.raises(KeyError):
        report.by_name("does-not-exist")


def _strip_latency(result: StrategyResult) -> tuple[str, float, float, float, float, float]:
    return (
        result.name,
        result.avg_context_tokens,
        result.avg_total_tokens,
        result.avg_round_trips,
        result.concept_recall,
        result.keyword_recall,
    )
