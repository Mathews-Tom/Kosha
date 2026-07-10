"""``--json`` structured output across validate/bench/eval/ingest/calibrate (M8 PR-1).

Every command's ``--json`` payload must (a) parse as JSON, (b) carry the same
verdict/counts the text renderer prints, and (c) never leak more than the text
path already does — in particular ``kosha ingest --json`` must not include raw
file content.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from kosha.bench.realworld import (
    DriftResult,
    MaintenanceResult,
    QueryStrategyResult,
    RealworldReport,
    SafetyResult,
)
from kosha.cli import main
from kosha.cli_json import bench_realworld_json
from kosha.providers.diagnostics import ProviderDiagnostic

ROOT = Path(__file__).resolve().parents[2]
NORTHWIND = ROOT / "bundles" / "northwind"
GOOD_BUNDLE = ROOT / "tests" / "fixtures" / "good_bundle"
BAD_BUNDLE = ROOT / "tests" / "fixtures" / "bad_bundle"


def _run_json(args: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, dict[str, Any]]:
    code = main(args)
    out = capsys.readouterr().out
    return code, json.loads(out)


# --- validate ----------------------------------------------------------------


def test_validate_json_reports_a_conformant_bundle(capsys: pytest.CaptureFixture[str]) -> None:
    code, payload = _run_json(["validate", str(GOOD_BUNDLE), "--json"], capsys)
    assert code == 0
    assert payload["conformant"] is True
    assert payload["error_count"] == 0
    assert payload["bundle"] == str(GOOD_BUNDLE)
    assert isinstance(payload["findings"], list)


def test_validate_json_reports_errors_and_a_nonzero_exit(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, payload = _run_json(["validate", str(BAD_BUNDLE), "--json"], capsys)
    assert code == 1
    assert payload["conformant"] is False
    assert payload["error_count"] > 0
    assert all("severity" in f and "rule" in f and "path" in f for f in payload["findings"])


# --- bench ---------------------------------------------------------------


def test_bench_json_over_northwind(capsys: pytest.CaptureFixture[str]) -> None:
    code, payload = _run_json(["bench", "--bundle", str(NORTHWIND), "--json"], capsys)
    assert code == 0
    assert payload["verdict"] in {"GO", "NO-GO"}
    assert {s["name"] for s in payload["strategies"]} == {"hybrid", "rag", "long_context"}
    assert all("id" in signal and "fired" in signal for signal in payload["kill_signals"])


def test_bench_json_with_report_path_stays_pure_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Regression: --report's "Wrote report to ..." confirmation must not leak
    # onto stdout and corrupt the JSON stream when combined with --json.
    report_path = tmp_path / "PREMISE_REPORT.md"
    code, payload = _run_json(
        ["bench", "--bundle", str(NORTHWIND), "--report", str(report_path), "--json"], capsys
    )
    assert code == 0
    assert payload["verdict"] in {"GO", "NO-GO"}
    assert report_path.is_file()


def test_bench_acceptance_json_matches_exit_code(capsys: pytest.CaptureFixture[str]) -> None:
    code, payload = _run_json(["bench", "acceptance", "--bundle", str(NORTHWIND), "--json"], capsys)
    assert (code == 0) is payload["passed"]
    assert len(payload["criteria"]) >= 1
    assert all("id" in c and "passed" in c for c in payload["criteria"])


def test_bench_acceptance_json_with_report_path_stays_pure_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report_path = tmp_path / "ACCEPTANCE_REPORT.md"
    code, payload = _run_json(
        [
            "bench",
            "acceptance",
            "--bundle",
            str(NORTHWIND),
            "--report",
            str(report_path),
            "--json",
        ],
        capsys,
    )
    assert (code == 0) is payload["passed"]
    assert report_path.is_file()


def test_bench_realworld_json_shape() -> None:
    # The full realworld harness needs a real corpus/query fixture set; the
    # payload builder is exercised directly against a constructed report
    # instead of paying for a full run.
    report = RealworldReport(
        embedding_provider="lexical-hash-256",
        generation_provider="extractive-3",
        embedding_diagnostic=ProviderDiagnostic(
            role="embedding",
            is_configured=False,
            source="default",
            provider_name="lexical-hash-256",
            vars=[],
            errors=[],
        ),
        generation_diagnostic=ProviderDiagnostic(
            role="generation",
            is_configured=False,
            source="default",
            provider_name="extractive-3",
            vars=[],
            errors=[],
        ),
        corpus_path="bundles/pydoc-stdlib",
        concept_count=42,
        query_count=6,
        queries=(
            QueryStrategyResult(
                name="hybrid",
                concept_recall=1.0,
                keyword_recall=1.0,
                avg_context_tokens=10.0,
                avg_total_tokens=20.0,
            ),
        ),
        maintenance=(
            MaintenanceResult(name="kosha_loop", correct=8, total=10, by_kind={}),
            MaintenanceResult(name="prompt_only", correct=6, total=10, by_kind={}),
        ),
        drift=DriftResult(
            ingests=50,
            accuracy_start=0.9,
            accuracy_end=0.9,
            fidelity_ok=True,
            seed_concepts=150,
            final_concepts=195,
            fidelity_targeter="lexical",
        ),
        safety=(
            SafetyResult(name="kosha_loop", cases=10, safe=10, silent_overwrites=0),
            SafetyResult(name="prompt_only", cases=10, safe=5, silent_overwrites=0),
        ),
    )
    payload = bench_realworld_json(Path("bundles/pydoc-stdlib"), report)
    assert payload["verdict"] == report.verdict
    assert payload["maintenance_delta"] == pytest.approx(report.maintenance_delta)
    assert payload["safety_delta"] == pytest.approx(report.safety_delta)
    assert payload["drift"]["grew"] is True
    assert payload["drift"]["fidelity_targeter"] == "lexical"


def test_bench_realworld_cli_json_end_to_end(capsys: pytest.CaptureFixture[str]) -> None:
    # Regression: --json must print exactly one JSON document with no leaked
    # human-readable text (the offline smoke command stays fast; see
    # tests/bench/test_gate0_smoke.py for the full pre-registered contract).
    code, payload = _run_json(
        [
            "bench",
            "realworld",
            "--corpus",
            str(ROOT / "bundles" / "pydoc-stdlib"),
            "--ingests",
            "5",
            "--max-queries",
            "6",
            "--seed-concepts",
            "12",
            "--json",
        ],
        capsys,
    )
    assert code == 0
    assert payload["verdict"] in {"GO", "NO-GO"}
    assert payload["concept_count"] > 0


def test_bench_realworld_text_mode_prints_the_header_once(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Regression: a leftover unconditional print block duplicated every line
    # of the summary in text mode.
    code = main(
        [
            "bench",
            "realworld",
            "--corpus",
            str(ROOT / "bundles" / "pydoc-stdlib"),
            "--ingests",
            "5",
            "--max-queries",
            "6",
            "--seed-concepts",
            "12",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert out.count("Real-model benchmark over") == 1
    assert out.count("Gate 0 verdict:") == 1


# --- calibrate -------------------------------------------------------------


def test_calibrate_json(capsys: pytest.CaptureFixture[str]) -> None:
    code, payload = _run_json(["calibrate", "--json"], capsys)
    assert code == 0
    for surface in ("adjudicator", "targeter", "relator"):
        assert "threshold" in payload[surface]
        assert "case_count" in payload[surface]
    assert "high" in payload["embedding"]
    assert "low" in payload["embedding"]


# --- eval --------------------------------------------------------------------


def test_eval_extract_json(capsys: pytest.CaptureFixture[str]) -> None:
    code, payload = _run_json(["eval", "extract", "--json"], capsys)
    assert code == 0
    assert 0.0 <= payload["score"] <= 1.0
    assert payload["label_count"] > 0


def test_eval_dedup_json(capsys: pytest.CaptureFixture[str]) -> None:
    code, payload = _run_json(["eval", "dedup", "--json"], capsys)
    assert code == 0
    assert 0.0 <= payload["precision"] <= 1.0
    assert 0.0 <= payload["duplicate_rate"]["rate"] <= 1.0


def test_eval_merge_json(capsys: pytest.CaptureFixture[str]) -> None:
    code, payload = _run_json(["eval", "merge", "--json"], capsys)
    assert code == 0
    assert 0.0 <= payload["score"] <= 1.0


def test_eval_relate_json(capsys: pytest.CaptureFixture[str]) -> None:
    code, payload = _run_json(["eval", "relate", "--json"], capsys)
    assert code == 0
    assert 0.0 <= payload["f1"] <= 1.0


def test_eval_contradict_json(capsys: pytest.CaptureFixture[str]) -> None:
    code, payload = _run_json(["eval", "contradict", "--json"], capsys)
    assert code == 0
    assert 0.0 <= payload["f1"] <= 1.0
    assert isinstance(payload["by_regime"], dict)
    assert len(payload["by_regime"]) > 0


# --- ingest ------------------------------------------------------------------


def _seed_bundle(root: Path) -> None:
    from kosha.git_store import GitStore

    store = GitStore.init(root)
    (root / "index.md").write_text('okf_version: "0.1"\n', encoding="utf-8")
    store.commit(["index.md"], "chore: seed")


def test_ingest_json_dry_run_never_writes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = tmp_path / "bundle"
    source = tmp_path / "source"
    source.mkdir()
    _seed_bundle(bundle)
    (source / "widget.md").write_text(
        "# Widget Policy\n\nWidgets ship within 3 business days of order confirmation.\n",
        encoding="utf-8",
    )
    code, payload = _run_json(
        ["ingest", str(source), "--bundle", str(bundle), "--dry-run", "--json"], capsys
    )
    assert code == 0
    assert payload["dry_run"] is True
    assert payload["committed"] is False
    assert payload["commit_sha"] is None
    assert payload["plan"]["change_count"] >= 1
    change = payload["plan"]["changes"][0]
    assert set(change) == {
        "path",
        "kind",
        "summary",
        "concept_id",
        "confidence",
        "impact",
        "contradiction",
    }
    # file content is never included in the JSON payload
    assert "content" not in change


def test_ingest_json_committed_reports_refs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = tmp_path / "bundle"
    source = tmp_path / "source"
    source.mkdir()
    _seed_bundle(bundle)
    (source / "widget.md").write_text(
        "# Widget Policy\n\nWidgets ship within 3 business days of order confirmation.\n",
        encoding="utf-8",
    )
    code, payload = _run_json(
        ["ingest", str(source), "--bundle", str(bundle), "--yes", "--json"], capsys
    )
    assert code == 0
    assert payload["committed"] is True
    assert payload["decision"] == "approve"
    assert payload["commit_sha"] is not None
    assert payload["branch"] is not None
    assert payload["backup_tag"] is not None
    assert payload["routing"]["lane"] in {"auto", "skim", "review", "block"}
