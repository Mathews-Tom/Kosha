"""M2 sync CLI shell tests.

PR-1 only wires the ``kosha sync check`` command shell, the structured
mismatch/report model, and the text/JSON renderers. No real surface checker
is registered yet, so ``run_sync_check`` always runs with an empty checker
list unless the caller supplies one directly -- that is exactly what these
tests exercise. Real checkers (CLI reference, status, fallback, public
claims) land in later PRs and are out of scope here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kosha.cli import main
from kosha.sync import (
    SyncMismatch,
    render_sync_check_text,
    run_sync_check,
    sync_check_json,
)


def test_run_sync_check_with_no_checkers_reports_ok_and_passes_in_text(
    tmp_path: Path,
) -> None:
    report = run_sync_check(tmp_path)

    assert report.ok is True
    assert report.mismatches == ()
    assert render_sync_check_text(report) == (
        "Kosha sync check passed: generated surfaces match source-of-truth data."
    )


def _stale_reference_checker(root: Path) -> list[SyncMismatch]:
    return [
        SyncMismatch(
            surface="cli-reference",
            path=root / "docs" / "cli-reference.md",
            message="stale flag list",
            details=("missing --json",),
        )
    ]


def test_run_sync_check_surfaces_a_checker_mismatch_in_report_json_and_text(
    tmp_path: Path,
) -> None:
    report = run_sync_check(tmp_path, checkers=[_stale_reference_checker])

    assert report.ok is False
    assert report.mismatches == (
        SyncMismatch(
            surface="cli-reference",
            path=tmp_path.resolve() / "docs" / "cli-reference.md",
            message="stale flag list",
            details=("missing --json",),
        ),
    )

    payload = sync_check_json(report)
    assert payload == {
        "ok": False,
        "mismatch_count": 1,
        "mismatches": [
            {
                "surface": "cli-reference",
                "path": (tmp_path.resolve() / "docs" / "cli-reference.md").as_posix(),
                "message": "stale flag list",
                "details": ["missing --json"],
            }
        ],
    }

    text = render_sync_check_text(report)
    assert "Kosha sync check failed:" in text
    assert (tmp_path.resolve() / "docs" / "cli-reference.md").as_posix() in text
    assert "cli-reference: stale flag list" in text
    assert "missing --json" in text


def test_cli_sync_check_exits_zero_and_prints_pass_text(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(["sync", "check"])
    assert code == 0
    assert "Kosha sync check passed" in capsys.readouterr().out


def test_cli_sync_check_json_prints_parseable_ok_payload(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(["sync", "check", "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"ok": True, "mismatch_count": 0, "mismatches": []}


def test_cli_sync_with_no_subcommand_exits_two_and_requires_a_subcommand(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(["sync"])
    assert code == 2
    assert "kosha: sync requires a subcommand: check" in capsys.readouterr().err
