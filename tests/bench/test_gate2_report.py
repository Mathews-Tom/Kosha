"""The Gate-0 v2 report renderer and CLI command (spike S2)."""

from __future__ import annotations

from pathlib import Path

from kosha.bench.gate2.auditability import AuditabilityResult
from kosha.bench.gate2.criterion import (
    AxisDistribution,
    CellResult,
    Gate2Criterion,
    Gate2Report,
)
from kosha.bench.gate2.distribution import aggregate
from kosha.bench.gate2.report import render_gate2_report
from kosha.cli import main

_CRITERION = Gate2Criterion.preregistered()
_AUDIT = AuditabilityResult(
    guarantee_cases=108,
    guarantee_violations=0,
    supersede_lineage_ok=True,
    branch_per_ingest_ok=True,
)


def _axis(name: str, loop: list[float], prompt: list[float]) -> AxisDistribution:
    return AxisDistribution(name, aggregate(loop), aggregate(prompt))


def _cell(embed: str, gen: str, loop: list[float], prompt: list[float]) -> CellResult:
    return CellResult(
        embedding_label=embed,
        generation_label=gen,
        axes=(_axis("safety_rate", loop, prompt),),
        loop_silent_overwrites=0,
        contradictions=108,
        regimes=_CRITERION.regimes,
    )


def _report(loop: list[float], prompt: list[float], *, audit: bool) -> Gate2Report:
    cells = tuple(
        _cell(embed, gen, loop, prompt)
        for embed in ("bge-m3", "nomic")
        for gen in ("gpt-4o-mini", "gemma4")
    )
    return Gate2Report(
        criterion=_CRITERION,
        cells=cells,
        embeddings=("bge-m3", "nomic"),
        generations=("gpt-4o-mini", "gemma4"),
        runs=3,
        audit_verified=audit,
    )


def _render(report: Gate2Report) -> str:
    return render_gate2_report(
        report, _AUDIT, corpus_path="bundles/pydoc-stdlib", concept_count=680
    )


def test_render_go_report_states_authorization() -> None:
    report = _report([0.95, 0.97, 0.96], [0.60, 0.62, 0.58], audit=True)
    assert report.verdict == "GO"
    text = _render(report)
    assert "Verdict: GO" in text
    assert "M14+ authorized: True" in text
    assert "safety_rate" in text
    assert "noise band" in text  # criterion echoed
    assert "Branch-per-ingest provenance replayable: yes" in text


def test_render_nogo_report_lists_reasons() -> None:
    report = _report([0.64, 0.66, 0.65], [0.60, 0.62, 0.61], audit=True)
    assert report.verdict == "NO-GO"
    text = _render(report)
    assert "Verdict: NO-GO" in text
    assert "M14+ authorized: False" in text
    assert "did not beat a good prompt" in text


def test_cli_gate2_offline_writes_report_and_returns_nogo(tmp_path: Path) -> None:
    report_path = tmp_path / "GATE2.md"
    # Offline default providers => a 1x1 matrix: underpowered, so a guaranteed NO-GO.
    code = main(["bench", "realworld", "--gate2", "--runs", "1", "--report", str(report_path)])
    assert code == 1
    text = report_path.read_text(encoding="utf-8")
    assert "# Kosha Gate-0 v2 Re-Test" in text
    assert "Verdict: NO-GO" in text
    assert "Per-axis distributions" in text
    assert "detection_recall" in text
