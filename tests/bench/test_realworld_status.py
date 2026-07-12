"""Tests for rendering the tracked Gate-0 status doc update from a report (M3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from kosha.bench.realworld import (
    InvalidGate0VerdictError,
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


def test_gate0_status_doc_carries_the_s2v3_matrix_evidence() -> None:
    doc = DOCS_GATE0_STATUS.read_text(encoding="utf-8")
    assert "| S2-v3 Gate-0 (`edbe91b`, 2026-07-09) |" in doc
    assert "openai:gpt-4.1-nano" in doc
    assert "qwen:qwen3-235b-a22b-2507" in doc


def test_gate0_status_doc_discloses_the_s2v3_thin_sample_caveat() -> None:
    # The S2-v3 powered run sampled zero contradiction cases and one held-out
    # query -- far thinner than the 108-case S2 Gate-0 v2 run. A bare 0.00
    # safety-rate row would misread as a strong loss; the doc must disclose
    # the empty sample instead of letting that number stand unqualified.
    doc = DOCS_GATE0_STATUS.read_text(encoding="utf-8")
    assert "0 contradiction cases" in doc
    assert "1 held-out query" in doc
    assert "thin" in doc.lower()


def _stub_report(*, verdict_no_go: bool, local_providers: bool = False) -> RealworldReport:
    loop_safe, prompt_safe = (3, 8) if verdict_no_go else (9, 3)
    embedding_provider = "lexical-hash-256" if local_providers else "stub-embed"
    generation_provider = "extractive-3" if local_providers else "stub-gen"
    return RealworldReport(
        embedding_provider=embedding_provider,
        generation_provider=generation_provider,
        embedding_diagnostic=ProviderDiagnostic(
            "embedding", False, "default", embedding_provider, [], []
        ),
        generation_diagnostic=ProviderDiagnostic(
            "generation", False, "default", generation_provider, [], []
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


def test_render_gate_status_summary_rejects_an_invalid_local_provider_verdict() -> None:
    # A full-scale run measured with local providers is not a valid Gate-0
    # result (PR-1: reject local-provider verdicts); the status renderer must
    # refuse to turn it into public GO/NO-GO text rather than silently
    # publishing a misleading verdict.
    report = _stub_report(verdict_no_go=True, local_providers=True)
    assert report.verdict == "INVALID (local providers)"
    with pytest.raises(InvalidGate0VerdictError, match="NOT a valid Gate-0 verdict"):
        render_gate_status_summary(report)


def test_render_gate_status_row_rejects_an_invalid_local_provider_verdict() -> None:
    report = _stub_report(verdict_no_go=False, local_providers=True)
    assert report.verdict == "INVALID (local providers)"
    with pytest.raises(InvalidGate0VerdictError, match="NOT a valid Gate-0 verdict"):
        render_gate_status_row(
            report,
            run_label="S2-v3 smoke",
            commit="abc1234",
            date="2026-07-09",
        )
