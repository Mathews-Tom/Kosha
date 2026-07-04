"""Gate-0 v2 re-run smoke fixtures (M3, DEVELOPMENT_PLAN §4 M3 verification).

Two commands are pre-registered as verification: an offline smoke —
``kosha bench realworld --ingests 5 --max-queries 6`` — that must stay
deterministic under the local providers, and a full-scale run — ``--ingests
50`` — that is only a valid recorded Gate-0 verdict with real providers
configured. This module locks in both contracts against the exact CLI
entrypoint, not just the underlying runner function.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kosha.cli import main

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "bundles" / "pydoc-stdlib"


def _run_cli(report_path: Path, *, ingests: int, max_queries: int) -> int:
    return main(
        [
            "bench",
            "realworld",
            "--corpus",
            str(CORPUS),
            "--ingests",
            str(ingests),
            "--max-queries",
            str(max_queries),
            "--seed-concepts",
            "12",
            "--report",
            str(report_path),
        ]
    )


def test_offline_smoke_exits_zero_and_records_a_verdict(tmp_path: Path) -> None:
    report_path = tmp_path / "ACCEPTANCE_REPORT.md"
    code = _run_cli(report_path, ingests=5, max_queries=6)
    assert code == 0
    text = report_path.read_text(encoding="utf-8")
    assert "**Verdict: GO**" in text or "**Verdict: NO-GO**" in text


def test_offline_smoke_is_deterministic(tmp_path: Path) -> None:
    # Local lexical/extractive providers are deterministic, so re-running the
    # exact pre-registered smoke command must reproduce the same report.
    first = tmp_path / "first.md"
    second = tmp_path / "second.md"
    assert _run_cli(first, ingests=5, max_queries=6) == 0
    assert _run_cli(second, ingests=5, max_queries=6) == 0
    assert first.read_text(encoding="utf-8") == second.read_text(encoding="utf-8")


def test_offline_smoke_does_not_warn_about_local_providers(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Below the real Gate-0 ingest threshold, local providers are expected and
    # must not be flagged as an invalid Gate-0 attempt.
    assert _run_cli(tmp_path / "report.md", ingests=5, max_queries=6) == 0
    assert "NOT a valid Gate-0 verdict" not in capsys.readouterr().err


def test_full_scale_run_without_real_providers_warns_instead_of_a_silent_verdict(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # DEVELOPMENT_PLAN M3 gap: "a GO/NO-GO verdict is only valid when real
    # providers are configured." A full-scale (>=MIN_INGESTS) attempt with the
    # default local providers must exit 0 (it is still a runnable smoke) but
    # loudly say the result is not a valid recorded Gate-0 verdict.
    code = _run_cli(tmp_path / "report.md", ingests=50, max_queries=2)
    assert code == 0
    assert "NOT a valid Gate-0 verdict" in capsys.readouterr().err
