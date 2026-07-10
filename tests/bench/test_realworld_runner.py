"""Offline tests for the real-model runner driven by deterministic local providers.

The runner is exercised end to end against the committed corpus and held-out sets
with the lexical embedding and extractive generation providers and a tiny ingest
count, so the three-way table, the maintenance comparison, the drift probe, and
the verdict all render without a network call. The numbers are weak (that is the
whole point of M13 — local providers are not a real model); only the structure
and the verdict plumbing are asserted here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kosha.bench.realworld import (
    RealworldConfig,
    render_realworld_report,
    run_realworld,
)
from kosha.bench.realworld.runner import KILL_CRITERION, MIN_INGESTS
from kosha.cli import main
from kosha.contradiction import LexicalContradictionJudge
from kosha.dedup import LexicalAdjudicator
from kosha.providers import ExtractiveGenerationProvider, LexicalEmbeddingProvider
from kosha.telemetry import InMemoryTelemetrySink

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "bundles" / "pydoc-stdlib"
QUERIES = ROOT / "evals" / "realworld" / "queries.jsonl"
MAINTENANCE = ROOT / "evals" / "realworld" / "maintenance.jsonl"
GUIDANCE = ROOT / "consumer" / "AGENTS.fragment.md"


def _config(ingests: int = 2) -> RealworldConfig:
    return RealworldConfig(
        corpus=CORPUS,
        queries=QUERIES,
        maintenance=MAINTENANCE,
        guidance=GUIDANCE,
        ingests=ingests,
        candidate_k=4,
        drift_seed_concepts=12,
        max_queries=4,
    )


def _run(work_dir: Path, ingests: int = 2):  # type: ignore[no-untyped-def]
    return run_realworld(
        _config(ingests),
        LexicalEmbeddingProvider(),
        ExtractiveGenerationProvider(),
        adjudicator=LexicalAdjudicator(),
        judge=LexicalContradictionJudge(),
        work_dir=work_dir,
    )


def test_runner_produces_three_way_and_maintenance(tmp_path: Path) -> None:
    report = _run(tmp_path)
    assert {r.name for r in report.queries} == {"kosha_hybrid", "tuned_rag", "prompt_only"}
    assert {r.name for r in report.maintenance} == {"kosha_loop", "prompt_only"}
    assert report.query_count == 4
    assert report.concept_count >= 500
    # The reframed moat metric: loop vs prompt-only knowledge-integrity safety.
    assert {r.name for r in report.safety} == {"kosha_loop", "prompt_only"}
    # The loop's reconcile guarantee never silently overwrites a prior claim.
    assert report.safety_by_name("kosha_loop").silent_overwrites == 0


def test_realworld_runner_emits_provider_token_telemetry(tmp_path: Path) -> None:
    sink = InMemoryTelemetrySink()

    report = run_realworld(
        _config(ingests=1),
        LexicalEmbeddingProvider(),
        ExtractiveGenerationProvider(),
        adjudicator=LexicalAdjudicator(),
        judge=LexicalContradictionJudge(),
        work_dir=tmp_path,
        telemetry_sink=sink,
    )

    assert len(sink.records) == report.query_count * 3
    assert {record["kind"] for record in sink.records} == {"provider"}
    assert all("total_tokens" in record for record in sink.records)
    assert all("body" not in record and "text" not in record for record in sink.records)


def test_runner_drift_grows_the_corpus(tmp_path: Path) -> None:
    report = _run(tmp_path, ingests=2)
    assert report.drift.ingests == 2
    # Distinct growth docs must each create a concept, so the corpus actually grows
    # (the bug the review caught: integer-only docs dedupe-collapse and never grow).
    assert report.drift.concepts_added == 2
    assert report.drift.final_concepts == report.drift.seed_concepts + 2
    assert report.drift.grew
    # The edit-drift fidelity probe always runs the full >=50-ingest check.
    assert report.drift.fidelity_ok
    # Default config keeps the deterministic lexical-Jaccard targeter.
    assert report.drift.fidelity_targeter.startswith("lexical-jaccard-")


def test_runner_records_generation_fidelity_targeter_identity(tmp_path: Path) -> None:
    # M4: the drift probe's fidelity_targeter must reflect the configured
    # generation targeter and the provider identity it used, not just "lexical",
    # so a real-model run cannot be mistaken for the deterministic default.
    config = RealworldConfig(
        corpus=CORPUS,
        queries=QUERIES,
        maintenance=MAINTENANCE,
        guidance=GUIDANCE,
        ingests=1,
        candidate_k=4,
        drift_seed_concepts=12,
        max_queries=1,
        fidelity_targeter="generation",
    )
    report = run_realworld(
        config,
        LexicalEmbeddingProvider(),
        ExtractiveGenerationProvider(),
        adjudicator=LexicalAdjudicator(),
        judge=LexicalContradictionJudge(),
        work_dir=tmp_path,
    )
    assert report.drift.fidelity_targeter.startswith("generation:")
    assert "extractive-3" in report.drift.fidelity_targeter


def test_render_report_has_table_kill_criterion_and_verdict(tmp_path: Path) -> None:
    report = _run(tmp_path)
    document = render_realworld_report(report)
    assert "kosha-loop" in document
    assert "tuned-rag" in document
    assert "prompt-only" in document
    assert "## Drift across sequential ingests" in document
    assert "Fidelity targeter:" in document
    assert "Knowledge-integrity safety" in document
    assert KILL_CRITERION in document
    assert report.verdict in {"GO", "NO-GO"}
    assert f"Verdict: {report.verdict}" in document


def test_render_report_includes_provider_diagnostics(tmp_path: Path) -> None:
    report = _run(tmp_path, ingests=2)
    document = render_realworld_report(report)
    assert "(default offline)" in document
    assert "lexical-hash" in document
    assert "extractive" in document


def test_verdict_rejects_local_providers_on_full_scale_run(tmp_path: Path) -> None:
    report = _run(tmp_path, ingests=50)  # MIN_INGESTS
    assert report.verdict == "INVALID (local providers)"


def test_verdict_requires_min_ingests(tmp_path: Path) -> None:
    # With only 2 ingests the >=50-ingest gate cannot pass, so a GO is impossible.
    report = _run(tmp_path, ingests=2)
    assert report.drift.ingests < MIN_INGESTS
    assert report.verdict == "NO-GO"


def test_cli_realworld_writes_report(tmp_path: Path) -> None:
    report_path = tmp_path / "ACCEPTANCE_REPORT.md"
    code = main(
        [
            "bench",
            "realworld",
            "--corpus",
            str(CORPUS),
            "--ingests",
            "1",
            "--max-queries",
            "2",
            "--seed-concepts",
            "12",
            "--report",
            str(report_path),
        ]
    )
    assert code == 0
    text = report_path.read_text(encoding="utf-8")
    assert "Real-Model Acceptance Report" in text
    assert "| Strategy |" in text


def test_cli_realworld_json_reports_generation_fidelity_targeter(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(
        [
            "bench",
            "realworld",
            "--corpus",
            str(CORPUS),
            "--ingests",
            "1",
            "--max-queries",
            "2",
            "--seed-concepts",
            "12",
            "--fidelity-targeter",
            "generation",
            "--json",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["drift"]["fidelity_targeter"].startswith("generation:")
    assert "extractive-3" in payload["drift"]["fidelity_targeter"]
