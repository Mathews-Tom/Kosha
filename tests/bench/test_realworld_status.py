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
    render_realworld_report,
    run_realworld,
)
from kosha.bench.realworld.runner import (
    DriftResult,
    MaintenanceResult,
    QueryStrategyResult,
    RealworldReport,
    SafetyResult,
)
from kosha.contradiction import LexicalContradictionJudge
from kosha.dedup import LexicalAdjudicator
from kosha.providers import ExtractiveGenerationProvider, LexicalEmbeddingProvider
from kosha.providers.diagnostics import EnvVarDiagnostic, ProviderDiagnostic

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "bundles" / "pydoc-stdlib"
QUERIES = ROOT / "evals" / "realworld" / "queries.jsonl"
MAINTENANCE = ROOT / "evals" / "realworld" / "maintenance.jsonl"
GUIDANCE = ROOT / "consumer" / "AGENTS.fragment.md"
DOCS_GATE0_STATUS = ROOT / "docs" / "gate0-status.md"
S2V3_REPORT_PATH = ROOT / ".docs" / "s2-v3-report.md"


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


def _s2v3_embedding_diag() -> ProviderDiagnostic:
    return ProviderDiagnostic(
        "embedding",
        True,
        "env",
        "openai:bge-m3",
        [
            EnvVarDiagnostic("KOSHA_EMBED_BASE_URL", True, "http://localhost:11434/v1", []),
            EnvVarDiagnostic("KOSHA_EMBED_MODEL", True, "bge-m3", []),
            EnvVarDiagnostic("KOSHA_EMBED_API_KEY", True, "unus...", []),
            EnvVarDiagnostic("KOSHA_EMBED_DIM", True, "1024", []),
        ],
        [],
    )


def _s2v3_generation_diag(model: str) -> ProviderDiagnostic:
    return ProviderDiagnostic(
        "generation",
        True,
        "env",
        f"openai:{model}",
        [
            EnvVarDiagnostic("KOSHA_GEN_BASE_URL", True, "https://openrouter.ai/api/v1", []),
            EnvVarDiagnostic("KOSHA_GEN_MODEL", True, model, []),
            EnvVarDiagnostic("KOSHA_GEN_API_KEY", True, "sk-or-v...4817", []),
        ],
        [],
    )


def _s2v3_openai_report() -> RealworldReport:
    """Pinned `openai/gpt-4.1-nano` cell from the S2-v3 provider-matrix rerun."""
    return RealworldReport(
        embedding_provider="openai:bge-m3",
        generation_provider="openai:openai/gpt-4.1-nano",
        embedding_diagnostic=_s2v3_embedding_diag(),
        generation_diagnostic=_s2v3_generation_diag("openai/gpt-4.1-nano"),
        corpus_path="bundles/paper-s2v3-corpus",
        concept_count=2,
        query_count=1,
        queries=(
            QueryStrategyResult("kosha_hybrid", 1.00, 1.00, 235, 255),
            QueryStrategyResult("tuned_rag", 1.00, 1.00, 235, 254),
            QueryStrategyResult("prompt_only", 1.00, 1.00, 247, 690),
        ),
        maintenance=(
            MaintenanceResult(
                "kosha_loop", 1, 1, {"duplicate": 0.0, "novel": 1.0, "contradiction": 0.0}
            ),
            MaintenanceResult(
                "prompt_only", 1, 1, {"duplicate": 0.0, "novel": 1.0, "contradiction": 0.0}
            ),
        ),
        drift=DriftResult(50, 1.0, 1.0, True, 2, 52, "lexical-jaccard-0.30"),
        safety=(
            SafetyResult("kosha_loop", 0, 0, 0),
            SafetyResult("prompt_only", 0, 0, 0),
        ),
    )


def _s2v3_qwen_report() -> RealworldReport:
    """Pinned `qwen/qwen3-235b-a22b-2507` cell from the S2-v3 provider-matrix rerun."""
    return RealworldReport(
        embedding_provider="openai:bge-m3",
        generation_provider="openai:qwen/qwen3-235b-a22b-2507",
        embedding_diagnostic=_s2v3_embedding_diag(),
        generation_diagnostic=_s2v3_generation_diag("qwen/qwen3-235b-a22b-2507"),
        corpus_path="bundles/paper-s2v3-corpus",
        concept_count=2,
        query_count=1,
        queries=(
            QueryStrategyResult("kosha_hybrid", 1.00, 1.00, 235, 272),
            QueryStrategyResult("tuned_rag", 1.00, 1.00, 235, 276),
            QueryStrategyResult("prompt_only", 1.00, 0.00, 247, 661),
        ),
        maintenance=(
            MaintenanceResult(
                "kosha_loop", 0, 1, {"duplicate": 0.0, "novel": 0.0, "contradiction": 0.0}
            ),
            MaintenanceResult(
                "prompt_only", 0, 1, {"duplicate": 0.0, "novel": 0.0, "contradiction": 0.0}
            ),
        ),
        drift=DriftResult(50, 1.0, 0.0, True, 2, 48, "lexical-jaccard-0.30"),
        safety=(
            SafetyResult("kosha_loop", 0, 0, 0),
            SafetyResult("prompt_only", 0, 0, 0),
        ),
    )


def _s2v3_matrix_report_text() -> str:
    return "\n".join(
        [
            "# Kosha S2-v3 Provider-Matrix Acceptance Report (M3, Gate 0)",
            "",
            (
                "**Verdict: NO-GO** - the stricter rerun satisfies the pre-registered "
                "provider-matrix shape (one embedding model and two generation models from "
                "different vendors) but still does not clear the reframed kill criterion; "
                "ship Kosha as an OSS skill and halt M14+."
            ),
            "",
            "## Matrix setup",
            "",
            "- Corpus: `bundles/paper-s2v3-corpus` (2 concepts, external)",
            "- Embedding provider: `openai:bge-m3` via local OpenAI-compatible Ollama endpoint",
            "- Generation providers:",
            (
                "  - `openai:openai/gpt-4.1-nano` via OpenRouter "
                "(OpenAI; $0.10/M input, $0.40/M output)"
            ),
            (
                "  - `openai:qwen/qwen3-235b-a22b-2507` via OpenRouter "
                "(Qwen; $0.09/M input, $0.10/M output)"
            ),
            "- Held-out queries per cell: 1",
            "- Maintenance cases per cell: 1",
            "- Held-out contradiction cases per cell: 0",
            "- Sequential ingests per cell: 50",
            "- Report provenance:",
            (
                "  - `openai/gpt-4.1-nano`: `/tmp/kosha-s2v3-openai-gpt-4.1-nano.md`, "
                "sha256 `f367f4f62883231cf3a777388ce61841e7a396a6e674b4e0a8f90a4bfd289819`"
            ),
            (
                "  - `qwen/qwen3-235b-a22b-2507`: `/tmp/kosha-s2v3-qwen-235b.md`, "
                "sha256 `86db8cd4b7072b32339968474cba1bf4521a7904cba04975e12aa6fdda078ef6`"
            ),
            "",
            "## Matrix verdict",
            "",
            (
                "Both generation-provider cells are NO-GO. `openai/gpt-4.1-nano` preserved "
                "maintenance accuracy across the 50-ingest drift path but had zero held-out "
                "contradiction cases, so it could not clear the safety-margin criterion. "
                "`qwen/qwen3-235b-a22b-2507` also had zero held-out contradiction cases and "
                "regressed maintenance accuracy from 1.00 to 0.00 across the 50-ingest drift "
                "path. Neither cell supports decision-quality or retrieval superiority claims."
            ),
            "",
            "## Cell: OpenAI GPT-4.1 Nano",
            "",
            render_realworld_report(_s2v3_openai_report()),
            "",
            "## Cell: Qwen Qwen3 235B A22B 2507",
            "",
            render_realworld_report(_s2v3_qwen_report()),
            "",
        ]
    )


def test_s2v3_matrix_report_renders_byte_identical_to_the_checked_in_powered_result() -> None:
    # Guards `.docs/s2-v3-report.md` from silent hand-edits after PR-4: the pinned
    # two-generation-provider matrix above must still render to exactly the committed report.
    committed = S2V3_REPORT_PATH.read_text(encoding="utf-8")
    assert _s2v3_matrix_report_text().strip() == committed.strip()
    assert _s2v3_openai_report().verdict == "NO-GO"
    assert _s2v3_qwen_report().verdict == "NO-GO"


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
