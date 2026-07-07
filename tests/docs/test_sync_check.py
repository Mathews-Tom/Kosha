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

Other checkers (fallback/MCP, public-claim integration) are out of scope
here; PR-3 adds ``check_gate0_status`` (Gate-0 verdict sentence drift) and
``check_readme_acceptance_table`` (README deterministic self-consistency
table drift), covered below alongside ``check_status_surfaces`` and the
``default_sync_checkers`` wiring. PR-4 adds ``check_traversal_surfaces``:
``check_mcp_integration_doc`` (``docs/mcp-integration.md`` tool table drift
against the live ``kosha.mcp.server`` registry tool surface) and
``check_fallback_artifacts`` (the committed ``consumer/`` fallback files
drift against ``kosha.mcp.fallback``'s rendered output). PR-5 wires
``check_public_claims`` (the M1 public claim-boundary guardrails) into
``default_sync_checkers``; its own drift coverage lives in
``tests/docs/test_public_claims.py``, exercised here only through the
``default_sync_checkers`` wiring assertion below.
"""

import json
import re
import shutil
import sys
from pathlib import Path

import pytest

from kosha.bench.realworld.status import render_gate_status_summary
from kosha.cli import build_parser, main
from kosha.mcp.fallback import render_consumer_skill, render_fallback_fragment
from kosha.sync import (
    SyncMismatch,
    default_sync_checkers,
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
from kosha.sync.status_surfaces import (
    DEFAULT_ACCEPTANCE_BUNDLE,
    GATE0_STATUS_PATH,
    check_gate0_status,
    check_readme_acceptance_table,
    check_status_surfaces,
    recorded_gate0_report,
    render_readme_acceptance_rows,
    run_default_acceptance_report,
)
from kosha.sync.traversal import (
    FALLBACK_FRAGMENT_PATH,
    FALLBACK_SKILL_PATH,
    MCP_DOC_PATH,
    check_fallback_artifacts,
    check_mcp_integration_doc,
    check_traversal_surfaces,
    live_mcp_tools,
    render_mcp_tool_rows,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_run_sync_check_with_no_checkers_reports_ok_and_passes_in_text(
    tmp_path: Path,
) -> None:
    report = run_sync_check(tmp_path, checkers=())

    assert report.ok is True
    assert report.mismatches == ()
    assert render_sync_check_text(report) == (
        "Kosha sync check passed: generated surfaces match source-of-truth data."
    )


def test_run_sync_check_default_checkers_actually_run_and_differ_from_no_checkers(
    tmp_path: Path,
) -> None:
    """``checkers=()`` is an explicit request to skip every check; leaving
    ``checkers`` unset must still dispatch to ``default_sync_checkers()``
    instead of silently behaving like ``checkers=()``."""
    no_check_report = run_sync_check(tmp_path, checkers=())
    assert no_check_report.ok is True
    assert no_check_report.mismatches == ()

    default_report = run_sync_check(tmp_path)
    assert default_report.ok is False
    assert default_report.mismatches, (
        "run_sync_check() with no checkers arg must dispatch to the real "
        "default checkers against an unaligned repo, not skip checking"
    )


def test_run_sync_check_with_no_checkers_arg_passes_against_this_repo() -> None:
    report = run_sync_check(REPO_ROOT)

    assert report.ok is True
    assert report.mismatches == ()


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


def _raising_checker(root: Path) -> list[SyncMismatch]:
    raise ValueError("boom: checker exploded")


def test_run_sync_check_converts_a_raising_checker_into_a_mismatch_and_keeps_going(
    tmp_path: Path,
) -> None:
    report = run_sync_check(
        tmp_path, checkers=[_raising_checker, _stale_reference_checker]
    )

    assert report.ok is False
    assert len(report.mismatches) == 2
    error_mismatch, stale_mismatch = report.mismatches

    assert error_mismatch.surface == "_raising_checker"
    assert error_mismatch.path == tmp_path.resolve()
    assert error_mismatch.message == "sync checker raised ValueError"
    assert error_mismatch.details == ("boom: checker exploded",)

    # the second checker still ran despite the first one raising.
    assert stale_mismatch.surface == "cli-reference"
    assert stale_mismatch.message == "stale flag list"


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
# check_gate0_status: docs/gate0-status.md "Current public verdict" drift
# against render_gate_status_summary(recorded_gate0_report()).
# ---------------------------------------------------------------------------


def test_check_gate0_status_returns_no_mismatches_for_the_recorded_verdict() -> None:
    assert check_gate0_status(REPO_ROOT) == ()


def test_check_gate0_status_flags_a_drifted_verdict_sentence_in_the_status_doc(
    tmp_path: Path,
) -> None:
    expected_summary = render_gate_status_summary(recorded_gate0_report())
    status_text = (REPO_ROOT / GATE0_STATUS_PATH).read_text(encoding="utf-8")
    assert expected_summary in status_text

    drifted_summary = expected_summary.replace("halted", "HALTED (drift)")
    drifted_text = status_text.replace(expected_summary, drifted_summary)
    assert expected_summary not in drifted_text

    (tmp_path / GATE0_STATUS_PATH.parent).mkdir(parents=True)
    (tmp_path / GATE0_STATUS_PATH).write_text(drifted_text, encoding="utf-8")

    mismatches = check_gate0_status(tmp_path)

    assert len(mismatches) == 1
    mismatch = mismatches[0]
    assert mismatch.surface == "gate0-status"
    assert mismatch.path == tmp_path / GATE0_STATUS_PATH
    assert mismatch.details == (expected_summary,)


# ---------------------------------------------------------------------------
# render_readme_acceptance_rows / check_readme_acceptance_table: README's
# deterministic self-consistency table drift against run_acceptance output.
# ---------------------------------------------------------------------------


def test_render_readme_acceptance_rows_produces_rows_present_in_the_readme() -> None:
    report = run_default_acceptance_report(REPO_ROOT)
    rows = render_readme_acceptance_rows(report)

    assert len(rows) == len(report.criteria)
    assert len(rows) >= 5
    readme_text = (REPO_ROOT / README_PATH).read_text(encoding="utf-8")
    for row in rows:
        assert row in readme_text


def _copy_reference_bundle(tmp_path: Path) -> None:
    shutil.copytree(
        REPO_ROOT / DEFAULT_ACCEPTANCE_BUNDLE, tmp_path / DEFAULT_ACCEPTANCE_BUNDLE
    )


def test_check_readme_acceptance_table_returns_no_mismatches_for_aligned_repo_docs() -> None:
    assert check_readme_acceptance_table(REPO_ROOT) == ()


def test_check_readme_acceptance_table_flags_a_missing_deterministic_status_row(
    tmp_path: Path,
) -> None:
    _copy_reference_bundle(tmp_path)
    rows = render_readme_acceptance_rows(run_default_acceptance_report(REPO_ROOT))
    dropped_row = rows[0]

    readme_text = (REPO_ROOT / README_PATH).read_text(encoding="utf-8")
    assert dropped_row in readme_text
    drifted_readme = readme_text.replace(dropped_row, "")
    assert dropped_row not in drifted_readme
    (tmp_path / README_PATH).write_text(drifted_readme, encoding="utf-8")

    mismatches = check_readme_acceptance_table(tmp_path)

    assert len(mismatches) == 1
    mismatch = mismatches[0]
    assert mismatch.surface == "readme-acceptance-table"
    assert mismatch.path == tmp_path / README_PATH
    assert mismatch.details == (f"missing row: {dropped_row}",)


# ---------------------------------------------------------------------------
# check_status_surfaces: both status-surface checkers wired together.
# ---------------------------------------------------------------------------


def test_check_status_surfaces_returns_no_mismatches_for_aligned_repo_docs() -> None:
    assert check_status_surfaces(REPO_ROOT) == ()


# ---------------------------------------------------------------------------
# live_mcp_tools / render_mcp_tool_rows: the live FastMCP registry-server
# tool surface parsed from kosha.mcp.server, and its docs table rendering.
# ---------------------------------------------------------------------------


def test_live_mcp_tools_includes_live_registry_tools_and_signatures() -> None:
    tools = {tool.name: tool for tool in live_mcp_tools()}

    assert tools["list_bundles"].signature == "()"
    assert (
        tools["find_concepts"].signature == "(bundle_id: str, query: str, k: int = 3)"
    )
    assert (
        tools["claim_history"].signature
        == "(bundle_id: str, concept_id: str, claim_id: str | None = None)"
    )


def test_live_mcp_tools_does_not_import_kosha_mcp_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``live_mcp_tools`` locates ``kosha.mcp.server``'s source file via
    ``importlib.util.find_spec`` and parses it with ``ast``; it must never
    actually import the module, since that module's own top-level import of
    the optional ``mcp`` SDK would make doc-sync fail on installs that don't
    have the ``mcp`` extra."""
    monkeypatch.delitem(sys.modules, "kosha.mcp.server", raising=False)

    tools = live_mcp_tools()

    assert "kosha.mcp.server" not in sys.modules
    assert {tool.name for tool in tools} >= {"list_bundles", "find_concepts"}


def test_render_mcp_tool_rows_produces_rows_present_in_mcp_integration_doc() -> None:
    rows = render_mcp_tool_rows()
    tool_names = {tool.name for tool in live_mcp_tools()}

    assert len(rows) == len(tool_names)
    assert {"list_bundles", "find_concepts", "claim_history"} <= tool_names
    doc_text = (REPO_ROOT / MCP_DOC_PATH).read_text(encoding="utf-8")
    for row in rows:
        assert row in doc_text


# ---------------------------------------------------------------------------
# check_mcp_integration_doc: docs/mcp-integration.md tool table drift against
# the live kosha.mcp.server registry tool surface.
# ---------------------------------------------------------------------------


def test_check_mcp_integration_doc_returns_no_mismatches_for_aligned_repo_docs() -> None:
    assert check_mcp_integration_doc(REPO_ROOT) == ()


def test_check_mcp_integration_doc_flags_a_tool_row_missing_from_the_doc(
    tmp_path: Path,
) -> None:
    claim_history_row = next(
        row for row in render_mcp_tool_rows() if row.startswith("| `claim_history`")
    )
    doc_text = (REPO_ROOT / MCP_DOC_PATH).read_text(encoding="utf-8")
    assert claim_history_row in doc_text
    drifted_text = doc_text.replace(claim_history_row, "")
    assert claim_history_row not in drifted_text

    (tmp_path / MCP_DOC_PATH.parent).mkdir(parents=True)
    (tmp_path / MCP_DOC_PATH).write_text(drifted_text, encoding="utf-8")

    mismatches = check_mcp_integration_doc(tmp_path)

    assert len(mismatches) == 1
    mismatch = mismatches[0]
    assert mismatch.surface == "mcp-integration"
    assert mismatch.path == tmp_path / MCP_DOC_PATH
    assert mismatch.details == (f"missing row: {claim_history_row}",)


# ---------------------------------------------------------------------------
# check_fallback_artifacts: consumer/AGENTS.fragment.md + consumer/kosha-
# traversal/SKILL.md drift against kosha.mcp.fallback's rendered output.
# ---------------------------------------------------------------------------


def test_check_fallback_artifacts_returns_no_mismatches_for_aligned_repo_files() -> None:
    assert check_fallback_artifacts(REPO_ROOT) == ()


def test_check_fallback_artifacts_flags_a_stale_committed_fallback_file(
    tmp_path: Path,
) -> None:
    (tmp_path / FALLBACK_SKILL_PATH.parent).mkdir(parents=True)
    (tmp_path / FALLBACK_FRAGMENT_PATH).write_text(
        render_fallback_fragment(), encoding="utf-8"
    )
    (tmp_path / FALLBACK_SKILL_PATH).write_text(
        render_consumer_skill() + "\nstale trailing text\n", encoding="utf-8"
    )

    mismatches = check_fallback_artifacts(tmp_path)

    assert len(mismatches) == 1
    mismatch = mismatches[0]
    assert mismatch.surface == "fallback-artifact"
    assert mismatch.path == tmp_path / FALLBACK_SKILL_PATH


# ---------------------------------------------------------------------------
# check_traversal_surfaces: the MCP-doc and fallback-artifact checkers wired
# together.
# ---------------------------------------------------------------------------


def test_check_traversal_surfaces_returns_no_mismatches_for_aligned_repo_docs() -> None:
    assert check_traversal_surfaces(REPO_ROOT) == ()


# ---------------------------------------------------------------------------
# default_sync_checkers: PR-3 wires the status-surface checker in alongside
# the CLI reference checker; PR-4 adds check_traversal_surfaces.
# ---------------------------------------------------------------------------


def test_default_sync_checkers_includes_all_four_registered_checkers() -> None:
    checker_names = {checker.__name__ for checker in default_sync_checkers()}
    assert {
        "check_cli_reference",
        "check_public_claims",
        "check_status_surfaces",
        "check_traversal_surfaces",
    } <= checker_names


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
