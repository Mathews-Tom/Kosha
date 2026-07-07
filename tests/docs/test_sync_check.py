"""M2 sync CLI checker tests.

PR-1 wired the ``kosha sync check`` command shell, the structured
mismatch/report model, and the text/JSON renderers with no real checker
registered. PR-2 registers the CLI reference checker as the (only, for now)
default checker, so ``kosha sync check`` now runs
``check_cli_reference`` against the live argparse command tree and the
checked-in ``docs/cli-reference.md``/``README.md``. These tests cover:

- ``live_cli_commands`` enumerating the live command tree from
  ``build_parser()``.
- ``render_cli_synopsis`` producing exactly the synopsis line checked into
  ``docs/cli-reference.md``.
- ``check_cli_reference`` passing against the (aligned) real repo docs, and
  catching a missing command in either ``docs/cli-reference.md`` or the
  README CLI overview table.

Other checkers (Gate-0/README status table, fallback/MCP, public-claim
integration) are out of scope here.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from kosha.cli import build_parser, main
from kosha.sync import (
    SyncMismatch,
    render_sync_check_text,
    run_sync_check,
    sync_check_json,
)
from kosha.sync.cli_reference import (
    CLI_REFERENCE_PATH,
    README_PATH,
    check_cli_reference,
    live_cli_commands,
    render_cli_synopsis,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


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


# ---------------------------------------------------------------------------
# live_cli_commands / render_cli_synopsis: the live argparse command tree.
# ---------------------------------------------------------------------------


def test_live_cli_commands_includes_representative_top_level_and_nested_commands() -> None:
    commands = live_cli_commands(build_parser())
    command_texts = {command.text for command in commands}

    top_level = {
        "kosha validate",
        "kosha bench",
        "kosha calibrate",
        "kosha eval",
        "kosha ingest",
        "kosha serve",
        "kosha review-queue",
        "kosha export",
        "kosha recover",
        "kosha sync",
        "kosha release",
    }
    assert top_level <= command_texts

    nested = {
        "kosha sync check",
        "kosha recover restore",
        "kosha review-queue decide",
        "kosha eval extract",
        "kosha eval dedup",
        "kosha eval merge",
        "kosha eval relate",
        "kosha eval contradict",
    }
    assert nested <= command_texts


def test_render_cli_synopsis_matches_checked_in_docs_synopsis() -> None:
    commands = live_cli_commands(build_parser())
    synopsis = render_cli_synopsis(commands)

    doc_text = (REPO_ROOT / CLI_REFERENCE_PATH).read_text(encoding="utf-8")
    match = re.search(r"^kosha \[--version\].*$", doc_text, re.MULTILINE)
    assert match is not None, (
        "expected a `kosha [--version] ...` synopsis line in docs/cli-reference.md"
    )
    assert synopsis == match.group(0)


# ---------------------------------------------------------------------------
# check_cli_reference: docs/cli-reference.md + README CLI overview drift.
# ---------------------------------------------------------------------------


def test_check_cli_reference_returns_no_mismatches_for_aligned_repo_docs() -> None:
    assert check_cli_reference(REPO_ROOT) == ()


def test_check_cli_reference_flags_a_command_missing_from_cli_reference_doc(
    tmp_path: Path,
) -> None:
    reference_text = (REPO_ROOT / CLI_REFERENCE_PATH).read_text(encoding="utf-8")
    drifted_reference = reference_text.replace("kosha sync check", "")
    assert "kosha sync check" not in drifted_reference

    (tmp_path / CLI_REFERENCE_PATH.parent).mkdir(parents=True)
    (tmp_path / CLI_REFERENCE_PATH).write_text(drifted_reference, encoding="utf-8")
    (tmp_path / README_PATH).write_text(
        (REPO_ROOT / README_PATH).read_text(encoding="utf-8"), encoding="utf-8"
    )

    mismatches = check_cli_reference(tmp_path)

    assert len(mismatches) == 1
    mismatch = mismatches[0]
    assert mismatch.surface == "cli-reference"
    assert mismatch.path == tmp_path / CLI_REFERENCE_PATH
    assert "missing live command: kosha sync check" in mismatch.details


def test_check_cli_reference_flags_a_command_missing_from_readme_overview(
    tmp_path: Path,
) -> None:
    readme_text = (REPO_ROOT / README_PATH).read_text(encoding="utf-8")
    drifted_readme = readme_text.replace("kosha eval dedup", "")
    assert "kosha eval dedup" not in drifted_readme

    (tmp_path / CLI_REFERENCE_PATH.parent).mkdir(parents=True)
    (tmp_path / CLI_REFERENCE_PATH).write_text(
        (REPO_ROOT / CLI_REFERENCE_PATH).read_text(encoding="utf-8"), encoding="utf-8"
    )
    (tmp_path / README_PATH).write_text(drifted_readme, encoding="utf-8")

    mismatches = check_cli_reference(tmp_path)

    assert len(mismatches) == 1
    mismatch = mismatches[0]
    assert mismatch.surface == "readme-cli-overview"
    assert mismatch.path == tmp_path / README_PATH
    assert "missing live command: kosha eval dedup" in mismatch.details


# ---------------------------------------------------------------------------
# CLI shell: now exercises the real default checker against this repo.
# ---------------------------------------------------------------------------


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
