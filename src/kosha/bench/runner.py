"""Run every strategy over the query set and aggregate tokens, latency, quality.

The runner builds the embedding index once, then for each strategy and query
retrieves context, generates an answer, and records token usage, wall-clock
latency, model round-trips, and grades. Token and quality figures are
deterministic (fixed corpus, fixed queries, deterministic local providers);
latency is wall-clock and therefore environment-dependent.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from time import perf_counter

from kosha.bench.grade import QueryGrade, grade_query
from kosha.bench.queries import NORTHWIND_QUERIES, BenchQuery
from kosha.bench.strategies import (
    HybridStrategy,
    LongContextStrategy,
    RagStrategy,
    RetrievalStrategy,
)
from kosha.index import EmbeddingIndex
from kosha.model import Bundle
from kosha.providers.base import EmbeddingProvider, GenerationProvider
from kosha.providers.tokens import count_tokens
from kosha.telemetry import TelemetrySink, TokenCost, emit_provider_call

# Strategy display order in every table and report.
STRATEGY_ORDER = ("hybrid", "rag", "long_context")


@dataclass(frozen=True)
class StrategyResult:
    """Aggregated metrics for one strategy across the whole query set."""

    name: str
    avg_context_tokens: float
    avg_total_tokens: float
    avg_round_trips: float
    avg_latency_ms: float
    concept_recall: float
    keyword_recall: float
    answered_fraction: float


@dataclass(frozen=True)
class BenchReport:
    """The full benchmark outcome: provider identities + per-strategy results."""

    embedding_provider: str
    generation_provider: str
    query_count: int
    results: tuple[StrategyResult, ...]

    def by_name(self, name: str) -> StrategyResult:
        for result in self.results:
            if result.name == name:
                return result
        raise KeyError(name)


def run_benchmark(
    bundle: Bundle,
    embedding_provider: EmbeddingProvider,
    generation_provider: GenerationProvider,
    queries: tuple[BenchQuery, ...] = NORTHWIND_QUERIES,
    *,
    telemetry_sink: TelemetrySink | None = None,
) -> BenchReport:
    """Benchmark hybrid / RAG / long-context over ``queries`` on ``bundle``."""
    index = EmbeddingIndex.build(bundle, embedding_provider)
    strategies: tuple[RetrievalStrategy, ...] = (
        HybridStrategy(bundle, index),
        RagStrategy(bundle, embedding_provider),
        LongContextStrategy(bundle),
    )
    results = tuple(
        _run_strategy(strategy, generation_provider, queries, telemetry_sink=telemetry_sink)
        for strategy in strategies
    )
    return BenchReport(
        embedding_provider=embedding_provider.name,
        generation_provider=generation_provider.name,
        query_count=len(queries),
        results=results,
    )


def _run_strategy(
    strategy: RetrievalStrategy,
    generation_provider: GenerationProvider,
    queries: tuple[BenchQuery, ...],
    *,
    telemetry_sink: TelemetrySink | None = None,
) -> StrategyResult:
    context_tokens: list[int] = []
    total_tokens: list[int] = []
    round_trips: list[int] = []
    latencies: list[float] = []
    grades: list[QueryGrade] = []
    for query in queries:
        start = perf_counter()
        context = strategy.retrieve(query.question)
        generation = generation_provider.generate(query.question, context.text)
        emit_provider_call(
            telemetry_sink,
            surface=f"bench.{strategy.name}",
            provider_name=generation_provider.name,
            usage=TokenCost(
                prompt_tokens=generation.usage.prompt_tokens,
                completion_tokens=generation.usage.completion_tokens,
                total_tokens=generation.usage.total_tokens,
            ),
        )
        latencies.append((perf_counter() - start) * 1000.0)
        context_tokens.append(count_tokens(context.text))
        total_tokens.append(generation.usage.total_tokens)
        # Generation is one further model round-trip on top of retrieval.
        round_trips.append(context.round_trips + 1)
        grades.append(grade_query(query, context, generation.text))
    return StrategyResult(
        name=strategy.name,
        avg_context_tokens=statistics.fmean(context_tokens),
        avg_total_tokens=statistics.fmean(total_tokens),
        avg_round_trips=statistics.fmean(round_trips),
        avg_latency_ms=statistics.fmean(latencies),
        concept_recall=statistics.fmean(g.concept_recall for g in grades),
        keyword_recall=statistics.fmean(g.keyword_recall for g in grades),
        answered_fraction=statistics.fmean(1.0 if g.answered else 0.0 for g in grades),
    )


def render_table(report: BenchReport) -> str:
    """Render the 3-strategy comparison as a GitHub-flavored Markdown table."""
    header = (
        "| Strategy | Avg context tokens | Avg total tokens | Retrieval+gen "
        "round-trips | Avg latency (ms) | Concept recall | Answer-keyword recall |"
    )
    divider = "|" + "|".join(["---"] * 7) + "|"
    rows = [header, divider]
    for name in STRATEGY_ORDER:
        result = report.by_name(name)
        rows.append(
            f"| {name} | {result.avg_context_tokens:.0f} | "
            f"{result.avg_total_tokens:.0f} | {result.avg_round_trips:.0f} | "
            f"{result.avg_latency_ms:.2f} | {result.concept_recall:.2f} | "
            f"{result.keyword_recall:.2f} |"
        )
    return "\n".join(rows)
