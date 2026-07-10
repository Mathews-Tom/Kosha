"""Tests for rendering the tracked Gate-0 status doc update from a report (M3)."""

from __future__ import annotations

from pathlib import Path

from kosha.bench.realworld import (
    RealworldConfig,
    local_provider_gate_warning,
    render_gate_status_row,
    render_gate_status_summary,
    run_realworld,
)
from kosha.bench.realworld.runner import (
    DriftResult,
    MaintenanceResult,
    RealworldReport,
    SafetyResult,
)
from kosha.contradiction import LexicalContradictionJudge
from kosha.dedup import LexicalAdjudicator
from kosha.providers import ExtractiveGenerationProvider, LexicalEmbeddingProvider
from kosha.providers.diagnostics import ProviderDiagnostic

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "bundles" / "pydoc-stdlib"
QUERIES = ROOT / "evals" / "realworld" / "queries.jsonl"
MAINTENANCE = ROOT / "evals" / "realworld" / "maintenance.jsonl"
GUIDANCE = ROOT / "consumer" / "AGENTS.fragment.md"
DOCS_GATE0_STATUS = ROOT / "docs" / "gate0-status.md"


def _report(work_dir: Path):  # type: ignore[no-untyped-def]
    config = RealworldConfig(
        corpus=CORPUS,
        queries=QUERIES,
        maintenance=MAINTENANCE,
        guidance=GUIDANCE,
        ingests=2,
        candidate_k=4,
        drift_seed_concepts=12,
        max_queries=4,
    )
    return run_realworld(
        config,
        LexicalEmbeddingProvider(),
        ExtractiveGenerationProvider(),
        adjudicator=LexicalAdjudicator(),
        judge=LexicalContradictionJudge(),
        work_dir=work_dir,
    )


def test_render_gate_status_summary_matches_the_recorded_verdict(tmp_path: Path) -> None:
    report = _report(tmp_path)
    summary = render_gate_status_summary(report)
    assert f"Real-model Gate-0 verdict: {report.verdict}" in summary
    if report.verdict == "NO-GO":
        assert "M14+ product expansion remains halted" in summary
    else:
        assert "M14+ product expansion may proceed" in summary


def test_gate0_status_doc_matches_the_current_recorded_verdict(tmp_path: Path) -> None:
    # docs/gate0-status.md's "Current public verdict" sentence must be exactly
    # what the renderer produces for the currently-recorded verdict (NO-GO,
    # per the S2 report) -- proving the doc is generated-and-pasted, not
    # hand-authored prose that can drift from what was actually measured.
    report = _report(tmp_path)
    assert report.verdict == "NO-GO", "update this test alongside a real GO verdict"
    summary = render_gate_status_summary(report)
    doc = DOCS_GATE0_STATUS.read_text(encoding="utf-8")
    assert summary in doc


def _stub_report(*, verdict_no_go: bool) -> RealworldReport:
    loop_safe, prompt_safe = (3, 8) if verdict_no_go else (9, 3)
    return RealworldReport(
        embedding_provider="stub-embed",
        generation_provider="stub-gen",
        embedding_diagnostic=ProviderDiagnostic(
            "embedding", False, "default", "stub-embed", [], []
        ),
        generation_diagnostic=ProviderDiagnostic(
            "generation", False, "default", "stub-gen", [], []
        ),
        corpus_path="stub-corpus",
        concept_count=500,
        query_count=0,
        queries=(),
        maintenance=(
            MaintenanceResult("kosha_loop", 8, 10, {}),
            MaintenanceResult("prompt_only", 8, 10, {}),
        ),
        drift=DriftResult(50, 0.8, 0.8, True, 100, 150, "lexical"),
        safety=(
            SafetyResult("kosha_loop", 10, loop_safe, 0),
            SafetyResult("prompt_only", 10, prompt_safe, 0),
        ),
    )


def test_render_gate_status_row_carries_setup_and_result() -> None:
    row = render_gate_status_row(
        _stub_report(verdict_no_go=True),
        run_label="M3 Gate-0 v2",
        commit="abc1234",
        date="2026-07-04",
    )
    assert row.startswith("| M3 Gate-0 v2 (`abc1234`, 2026-07-04) |")
    assert "stub-embed + stub-gen" in row
    assert "**NO-GO**" in row


def test_render_gate_status_summary_states_go_when_the_loop_wins() -> None:
    summary = render_gate_status_summary(_stub_report(verdict_no_go=False))
    assert "Real-model Gate-0 verdict: GO" in summary
    assert "M14+ product expansion may proceed" in summary


def test_local_provider_gate_warning_fires_at_real_gate0_scale() -> None:
    warning = local_provider_gate_warning("lexical-hash-256", "extractive-3", 50)
    assert warning is not None
    assert "NOT a valid Gate-0 verdict" in warning


def test_local_provider_gate_warning_is_silent_below_the_real_run_threshold() -> None:
    # The offline smoke (--ingests 5) is expected to use local providers.
    assert local_provider_gate_warning("lexical-hash-256", "extractive-3", 5) is None


def test_local_provider_gate_warning_is_silent_once_real_providers_are_configured() -> None:
    assert local_provider_gate_warning("openai:bge-m3", "openai:gpt-4o-mini", 50) is None


def test_local_provider_gate_warning_fires_if_only_one_side_is_real() -> None:
    # Gate-0 needs a real embedding AND a real generation model; a real
    # embedding paired with the local extractive generator is still not a
    # valid Gate-0 run.
    assert local_provider_gate_warning("openai:bge-m3", "extractive-3", 50) is not None
