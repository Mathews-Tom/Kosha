"""Tests for kill-signal evaluation and premise-report rendering."""

from __future__ import annotations

from pathlib import Path

from kosha.bench import (
    DedupSignal,
    GranularitySignal,
    evaluate_kill_signals,
    go_no_go,
    render_premise_report,
    run_benchmark,
)
from kosha.bench.runner import BenchReport, StrategyResult
from kosha.okf import load_bundle
from kosha.providers import ExtractiveGenerationProvider, LexicalEmbeddingProvider

NORTHWIND = Path(__file__).resolve().parents[2] / "bundles" / "northwind"


def _result(
    name: str,
    *,
    total_tokens: float,
    round_trips: float,
    latency: float,
    recall: float,
) -> StrategyResult:
    return StrategyResult(
        name=name,
        avg_context_tokens=total_tokens * 0.8,
        avg_total_tokens=total_tokens,
        avg_round_trips=round_trips,
        avg_latency_ms=latency,
        concept_recall=recall,
        keyword_recall=recall,
        answered_fraction=recall,
    )


def _report(
    *,
    hybrid_tokens: float,
    long_tokens: float,
    hybrid_recall: float,
    long_recall: float,
    hybrid_round_trips: float = 2,
    rag_round_trips: float = 2,
    hybrid_latency: float = 1.0,
    rag_latency: float = 1.0,
) -> BenchReport:
    return BenchReport(
        embedding_provider="test",
        generation_provider="test",
        query_count=8,
        results=(
            _result(
                "hybrid",
                total_tokens=hybrid_tokens,
                round_trips=hybrid_round_trips,
                latency=hybrid_latency,
                recall=hybrid_recall,
            ),
            _result(
                "rag",
                total_tokens=hybrid_tokens,
                round_trips=rag_round_trips,
                latency=rag_latency,
                recall=0.6,
            ),
            _result(
                "long_context",
                total_tokens=long_tokens,
                round_trips=1,
                latency=1.0,
                recall=long_recall,
            ),
        ),
    )


def _dedup(best_accuracy: float, ambiguous_errors: int) -> DedupSignal:
    return DedupSignal(
        pair_count=24,
        ambiguous_count=10,
        best_threshold=0.2,
        best_accuracy=best_accuracy,
        ambiguous_errors=ambiguous_errors,
    )


def _by_id(report: BenchReport, dedup: DedupSignal, signal_id: str) -> bool:
    signals = evaluate_kill_signals(report, dedup)
    return next(s for s in signals if s.id == signal_id).fired


def test_ks1_fires_only_when_long_context_matches_quality_at_low_cost() -> None:
    cheap = _report(hybrid_tokens=600, long_tokens=600, hybrid_recall=1.0, long_recall=1.0)
    assert _by_id(cheap, _dedup(0.7, 5), "KS1-long-context") is True
    expensive = _report(
        hybrid_tokens=600, long_tokens=1800, hybrid_recall=1.0, long_recall=1.0
    )
    assert _by_id(expensive, _dedup(0.7, 5), "KS1-long-context") is False


def test_ks2_fires_when_hybrid_costs_more_round_trips() -> None:
    base = {
        "hybrid_tokens": 600,
        "long_tokens": 1800,
        "hybrid_recall": 1.0,
        "long_recall": 1.0,
    }
    worse = _report(**base, hybrid_round_trips=5, rag_round_trips=2)
    assert _by_id(worse, _dedup(0.7, 5), "KS2-traversal-latency") is True
    parity = _report(**base, hybrid_round_trips=2, rag_round_trips=2)
    assert _by_id(parity, _dedup(0.7, 5), "KS2-traversal-latency") is False


def test_ks3_fires_when_threshold_only_closes_the_gap() -> None:
    report = _report(hybrid_tokens=600, long_tokens=1800, hybrid_recall=1.0, long_recall=1.0)
    assert _by_id(report, _dedup(0.98, 0), "KS3-dedup-by-prompt") is True
    assert _by_id(report, _dedup(0.75, 6), "KS3-dedup-by-prompt") is False


def test_go_no_go_is_no_go_when_any_signal_fires() -> None:
    fired = _report(hybrid_tokens=600, long_tokens=600, hybrid_recall=1.0, long_recall=1.0)
    assert go_no_go(evaluate_kill_signals(fired, _dedup(0.7, 5))) == "NO-GO"
    clean = _report(hybrid_tokens=600, long_tokens=1800, hybrid_recall=1.0, long_recall=1.0)
    assert go_no_go(evaluate_kill_signals(clean, _dedup(0.7, 5))) == "GO"


def test_rendered_report_states_verdict_and_every_signal() -> None:
    report = _report(hybrid_tokens=600, long_tokens=1800, hybrid_recall=1.0, long_recall=1.0)
    dedup = _dedup(0.75, 6)
    signals = evaluate_kill_signals(report, dedup)
    document = render_premise_report(
        bundle_path="bundles/northwind",
        concept_count=12,
        max_depth=3,
        report=report,
        dedup=dedup,
        granularity=GranularitySignal(label_count=8, correct=8),
        kill_signals=signals,
    )
    assert "Verdict: GO" in document
    assert "| hybrid |" in document
    for signal_id in ("KS1-long-context", "KS2-traversal-latency", "KS3-dedup-by-prompt"):
        assert signal_id in document


def test_real_northwind_run_passes_every_kill_signal() -> None:
    bundle = load_bundle(NORTHWIND)
    report = run_benchmark(
        bundle, LexicalEmbeddingProvider(), ExtractiveGenerationProvider()
    )
    # Real seed dedup signal: lexical thresholding cannot separate the labeled set.
    dedup = _dedup(0.75, 6)
    signals = evaluate_kill_signals(report, dedup)
    assert go_no_go(signals) == "GO"
