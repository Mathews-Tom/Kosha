"""Render the Gate-0 v2 re-test report (spike S2).

Lays out the pre-registered criterion, the provider matrix, the per-axis N-run
distributions per cell (median + interval, loop vs prompt-only, with the
noise-band and margin checks made explicit), the auditability acceptance result,
and the GO/NO-GO verdict with its M14+ consequence — derived strictly from the
fixed criterion, never adjusted to the numbers.
"""

from __future__ import annotations

from kosha.bench.gate2.auditability import AuditabilityResult
from kosha.bench.gate2.criterion import AxisDistribution, Gate2Report


def render_gate2_report(
    report: Gate2Report,
    auditability: AuditabilityResult,
    *,
    corpus_path: str,
    concept_count: int,
) -> str:
    """Render GATE2_REPORT.md from a Gate-0 v2 report and its auditability result."""
    criterion = report.criterion
    verdict = report.verdict
    consequence = (
        "GO authorizes M14+: the loop beat a good prompt on a buyer-relevant axis "
        "with the non-determinism noise band excluded."
        if verdict == "GO"
        else "NO-GO: keep Kosha a shipped OSS skill; M14+ stays halted."
    )
    lines = [
        "# Kosha Gate-0 v2 Re-Test",
        "",
        f"**Verdict: {verdict}** - {consequence}",
        "",
        f"**M14+ authorized: {report.authorizes_m14}**",
        "",
        "## Pre-registered criterion (fixed before measurement)",
        "",
        criterion.describe(),
        "",
        "## Setup",
        "",
        f"- Corpus: `{corpus_path}` ({concept_count} concepts, external)",
        f"- Embeddings: {_join(report.embeddings)}",
        f"- Generation models: {_join(report.generations)}",
        f"- Runs per cell: {report.runs}",
        f"- Held-out contradictions per cell: "
        f"{report.cells[0].contradictions if report.cells else 0}",
        f"- Regimes: {_join(report.cells[0].regimes) if report.cells else '(none)'}",
        "",
        "## Power (pre-registered admissibility)",
        "",
        f"- Provider matrix (>={criterion.min_embeddings}x{criterion.min_gen_models}): "
        f"{_ok(report.matrix_powered)}",
        f"- Sample size (>={criterion.min_contradictions}): {_ok(report.sample_powered)}",
        f"- Runs (>={criterion.min_runs}): {_ok(report.runs_powered)}",
        f"- Regime coverage ({len(criterion.regimes)}): {_ok(report.regimes_powered)}",
        f"- Loop never silently overwrites: {_ok(report.no_silent_overwrites)}",
        "",
        "## Per-axis distributions (median [min, max], loop vs prompt-only)",
        "",
        "| Embedding | Generation | Axis | Loop | Prompt-only | Δmedian | "
        "Noise excluded | Cleared |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for cell in report.cells:
        for axis in cell.axes:
            lines.append(
                _axis_row(
                    cell.embedding_label,
                    cell.generation_label,
                    axis,
                    criterion.quality_margin,
                )
            )
    lines.extend(
        [
            "",
            "## Auditability (necessary condition; a guarantee, not a quality win)",
            "",
            f"- No-silent-overwrite guarantee verified: "
            f"{_ok(auditability.guarantee_verified)} "
            f"({auditability.guarantee_cases} cases, "
            f"{auditability.guarantee_violations} violations)",
            f"- Claim supersede lineage replayable: {_ok(auditability.supersede_lineage_ok)}",
            f"- Branch-per-ingest provenance replayable: {_ok(auditability.branch_per_ingest_ok)}",
            "- Prompt-only equivalent: none - a prompt offers no machine-verifiable "
            "guarantee and no per-change branch/claim trail to replay, at any rate.",
            "",
            "## Decision",
            "",
            *_decision_lines(report),
            "",
        ]
    )
    return "\n".join(lines)


def _axis_row(
    embedding: str, generation: str, axis: AxisDistribution, margin: float
) -> str:
    loop = f"{axis.loop.median:.2f} [{axis.loop.lo:.2f}, {axis.loop.hi:.2f}]"
    prompt = f"{axis.prompt.median:.2f} [{axis.prompt.lo:.2f}, {axis.prompt.hi:.2f}]"
    return (
        f"| {embedding} | {generation} | {axis.axis} | {loop} | {prompt} | "
        f"{axis.median_delta:+.2f} | {_ok(axis.noise_band_excluded)} | "
        f"{_ok(axis.cleared(margin))} |"
    )


def _decision_lines(report: Gate2Report) -> list[str]:
    if report.verdict == "GO":
        axis = report.carrying_axis
        return [
            f"**Verdict: GO.** The `{axis}` axis cleared the pre-registered "
            f">={report.criterion.quality_margin:.0%} median margin with the "
            "non-determinism noise band excluded on every provider cell, the loop "
            "never silently overwrote, and the auditability guarantee held. M14+ is "
            "authorized.",
        ]
    reasons: list[str] = []
    if not report.matrix_powered:
        reasons.append("provider matrix underpowered (need >=2 embeddings x >=2 generations)")
    if not report.sample_powered:
        reasons.append("sample underpowered (need >=100 held-out contradictions per cell)")
    if not report.runs_powered:
        reasons.append("too few runs (need >=3 per cell to read the noise band)")
    if not report.regimes_powered:
        reasons.append("regime coverage incomplete")
    if not report.no_silent_overwrites:
        reasons.append("the loop silently overwrote a prior claim")
    if not report.auditability_ok:
        reasons.append("the auditability guarantee was not verified")
    if report.powered and report.no_silent_overwrites and report.auditability_ok:
        reasons.append(
            "no quality axis cleared the margin with the noise band excluded on every "
            "cell - the loop did not beat a good prompt at scale"
        )
    return [
        "**Verdict: NO-GO.** Kosha ships as an OSS skill; M14+ stays halted.",
        "",
        "Why:",
        *[f"- {reason}" for reason in reasons],
    ]


def _join(values: tuple[str, ...]) -> str:
    return ", ".join(values) if values else "(none)"


def _ok(value: bool) -> str:
    return "yes" if value else "no"
