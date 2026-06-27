"""Turn benchmark + dedup measurements into kill-signal verdicts and a report.

The three kill signals are the Premise-Validation gate (system_design §8.0,
DEVELOPMENT_PLAN §4 M4). Each verdict is derived from the measured numbers:

* **KS1 long-context** fires if long-context matches hybrid's quality *and* its
  token cost is within an acceptable multiple of hybrid's — i.e. the token-saving
  wedge is gone.
* **KS2 latency** fires if hybrid is not within a usable margin of one RAG hop
  (more retrieval round-trips, or materially higher wall-clock).
* **KS3 dedup-by-prompt** fires if a single similarity threshold already separates
  the labeled dedup pairs with no ambiguous residue — the loop adds nothing a
  prompt could not.

If any signal fires the verdict is NO-GO: stop and escalate the go/no-go decision
rather than proceeding to Sections C-F.
"""

from __future__ import annotations

from dataclasses import dataclass

from kosha.bench.labels import DedupSignal, GranularitySignal
from kosha.bench.runner import STRATEGY_ORDER, BenchReport, render_table

# A long-context run whose tokens stay within this multiple of hybrid's counts as
# "acceptable cost" — which (at matched quality) would retire the token wedge.
COST_MARGIN = 1.5
# Hybrid latency within this multiple of RAG's is a "usable margin".
LATENCY_MARGIN = 2.0
# Threshold-only dedup accuracy at or above this retires the loop's adjudication.
DEDUP_BAR = 0.95


@dataclass(frozen=True)
class KillSignal:
    """One gate signal: whether it fired, the verdict, and the evidence."""

    id: str
    question: str
    fired: bool
    verdict: str
    evidence: str


def evaluate_kill_signals(report: BenchReport, dedup: DedupSignal) -> list[KillSignal]:
    """Derive the three kill-signal verdicts from the measured numbers."""
    hybrid = report.by_name("hybrid")
    rag = report.by_name("rag")
    long_context = report.by_name("long_context")

    quality_matched = long_context.concept_recall >= hybrid.concept_recall - 1e-9
    cost_ratio = _ratio(long_context.avg_total_tokens, hybrid.avg_total_tokens)
    cost_acceptable = cost_ratio <= COST_MARGIN
    ks1_fired = quality_matched and cost_acceptable

    latency_ratio = _ratio(hybrid.avg_latency_ms, rag.avg_latency_ms)
    more_round_trips = hybrid.avg_round_trips > rag.avg_round_trips
    ks2_fired = more_round_trips or latency_ratio > LATENCY_MARGIN

    ks3_fired = dedup.best_accuracy >= DEDUP_BAR and dedup.ambiguous_errors == 0

    return [
        KillSignal(
            id="KS1-long-context",
            question="Does long-context-with-raw-docs match quality at acceptable cost?",
            fired=ks1_fired,
            verdict=_verdict(ks1_fired),
            evidence=(
                f"long-context concept recall {long_context.concept_recall:.2f} vs "
                f"hybrid {hybrid.concept_recall:.2f}; long-context costs "
                f"{cost_ratio:.2f}x hybrid total tokens "
                f"({long_context.avg_total_tokens:.0f} vs {hybrid.avg_total_tokens:.0f}); "
                f"acceptable-cost margin {COST_MARGIN}x. "
                "Token gap widens with corpus size (traversal cost is bounded by "
                "depth, not corpus size)."
            ),
        ),
        KillSignal(
            id="KS2-traversal-latency",
            question="Is hybrid within a usable latency margin of one RAG hop?",
            fired=ks2_fired,
            verdict=_verdict(ks2_fired),
            evidence=(
                f"hybrid {hybrid.avg_round_trips:.0f} retrieval+gen round-trips vs "
                f"RAG {rag.avg_round_trips:.0f}; hybrid latency "
                f"{hybrid.avg_latency_ms:.2f}ms vs RAG {rag.avg_latency_ms:.2f}ms "
                f"({latency_ratio:.2f}x, margin {LATENCY_MARGIN}x). Round-trip parity is "
                "deterministic; wall-clock is a local-compute proxy and should be "
                "re-confirmed against a network provider."
            ),
        ),
        KillSignal(
            id="KS3-dedup-by-prompt",
            question="Does a single similarity threshold close the dedup gap?",
            fired=ks3_fired,
            verdict=_verdict(ks3_fired),
            evidence=(
                f"best threshold-only accuracy {dedup.best_accuracy:.2f} at "
                f"cosine>={dedup.best_threshold:.3f} over {dedup.pair_count} pairs; "
                f"{dedup.ambiguous_errors}/{dedup.ambiguous_count} ambiguous-band pairs "
                f"still misclassified; bar {DEDUP_BAR:.2f}. Residual ambiguous band is "
                "where the loop's LLM adjudication earns its place."
            ),
        ),
    ]


def go_no_go(kill_signals: list[KillSignal]) -> str:
    """Return ``GO`` when no kill signal fired, else ``NO-GO``."""
    return "NO-GO" if any(signal.fired for signal in kill_signals) else "GO"


def render_premise_report(
    *,
    bundle_path: str,
    concept_count: int,
    max_depth: int,
    report: BenchReport,
    dedup: DedupSignal,
    granularity: GranularitySignal,
    kill_signals: list[KillSignal],
) -> str:
    """Render the full PREMISE_REPORT.md document."""
    verdict = go_no_go(kill_signals)
    lines = [
        "# Kosha Premise-Validation Report",
        "",
        f"**Verdict: {verdict}** "
        + (
            "- no kill signal fired; Sections C-F are authorized."
            if verdict == "GO"
            else "- a kill signal fired; halt Sections C-F and escalate the go/no-go."
        ),
        "",
        "## Setup",
        "",
        f"- Corpus: `{bundle_path}` ({concept_count} concepts, max path depth {max_depth})",
        f"- Queries: {report.query_count}",
        f"- Embedding provider: `{report.embedding_provider}`",
        f"- Generation provider: `{report.generation_provider}`",
        f"- Seed dedup pairs: {dedup.pair_count} "
        f"({dedup.ambiguous_count} ambiguous-band)",
        f"- Seed granularity labels: {granularity.label_count} "
        f"(lint accuracy {granularity.accuracy:.2f})",
        "",
        "Token and quality figures are deterministic (fixed corpus, fixed queries, "
        "deterministic local providers); latency is wall-clock and "
        "environment-dependent. `count_tokens` is a model-neutral estimate used for "
        "relative comparison.",
        "",
        "## Strategy comparison",
        "",
        render_table(report),
        "",
        "Strategy roles: **hybrid** and the embedding index are production-grade and "
        "reused downstream; **rag** and **long_context** are benchmark-only baselines.",
        "",
        "## Kill signals",
        "",
    ]
    for signal in kill_signals:
        lines.extend(
            [
                f"### {signal.id} — {signal.verdict}",
                "",
                f"_{signal.question}_",
                "",
                signal.evidence,
                "",
            ]
        )
    lines.extend(
        [
            "## Decision",
            "",
            f"All three kill signals: **{verdict}**. "
            + (
                "Proceed to M5+ (producer loop), re-anchoring claims on measured "
                "token savings, retrieval quality, and coherence/governance."
                if verdict == "GO"
                else "Do not proceed to M5+. Re-anchor the value proposition or stop, "
                "per the gating rule."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def _verdict(fired: bool) -> str:
    return "FAIL — kill signal fired" if fired else "PASS — premise holds"


def _ratio(numerator: float, denominator: float) -> float:
    if denominator == 0.0:
        return float("inf") if numerator > 0.0 else 1.0
    return numerator / denominator


__all__ = [
    "STRATEGY_ORDER",
    "KillSignal",
    "evaluate_kill_signals",
    "go_no_go",
    "render_premise_report",
]
