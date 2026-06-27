"""Premise-Validation benchmark harness (system_design §8.0).

Compares three retrieval strategies on the golden corpus — Kosha **hybrid**
(embedding-jump then traverse), a **RAG** chunk baseline, and a **long-context**
raw-docs baseline — on token cost, latency, and answer-supporting quality, and
turns the measurements into go/no-go kill-signal verdicts.

The hybrid strategy and the embedding index are production-grade and reused
downstream; the RAG and long-context strategies are benchmark-only baselines.
"""

from __future__ import annotations

from kosha.bench.grade import QueryGrade, grade_query
from kosha.bench.labels import (
    DedupPair,
    DedupSignal,
    GranularityLabel,
    GranularitySignal,
    evaluate_granularity,
    evaluate_threshold_only,
    load_dedup_pairs,
    load_granularity_labels,
)
from kosha.bench.queries import NORTHWIND_QUERIES, BenchQuery
from kosha.bench.report import (
    KillSignal,
    evaluate_kill_signals,
    go_no_go,
    render_premise_report,
)
from kosha.bench.runner import (
    STRATEGY_ORDER,
    BenchReport,
    StrategyResult,
    render_table,
    run_benchmark,
)
from kosha.bench.strategies import (
    HybridStrategy,
    LongContextStrategy,
    RagStrategy,
    RetrievalStrategy,
    RetrievedContext,
)

__all__ = [
    "NORTHWIND_QUERIES",
    "STRATEGY_ORDER",
    "BenchQuery",
    "BenchReport",
    "DedupPair",
    "DedupSignal",
    "GranularityLabel",
    "GranularitySignal",
    "HybridStrategy",
    "KillSignal",
    "LongContextStrategy",
    "QueryGrade",
    "RagStrategy",
    "RetrievalStrategy",
    "RetrievedContext",
    "StrategyResult",
    "evaluate_granularity",
    "evaluate_kill_signals",
    "evaluate_threshold_only",
    "go_no_go",
    "grade_query",
    "load_dedup_pairs",
    "load_granularity_labels",
    "render_premise_report",
    "render_table",
    "run_benchmark",
]
