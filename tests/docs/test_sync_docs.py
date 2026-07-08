"""M6 PR-1 scheduled sync workflow example: safety and scope guardrails.

``docs/examples/kosha-sync-pr.yml`` is a copy-to-enable GitHub Actions
workflow example: a scheduled ``kosha sync docs`` / ``kosha sync status``
refresh, verified with ``kosha sync check`` and ``kosha doctor providers``,
opened as a pull request via ``peter-evans/create-pull-request``. It lives
under ``docs/examples/`` (documentation only, inert until a maintainer
copies it into ``.github/workflows/``) and must stay safe-by-construction
for that copy-paste: it must never run ``kosha ingest``, never bypass
review with ``--yes``, never touch the BLOCK-lane review queue, and its
``create-pull-request`` ``add-paths`` must be scoped to exactly the
generated public surfaces the M2-M5 sync checkers own (never a broad
``docs/**``/``bundles/**``/``tests/**``/``src/**`` tree or the agent
instruction files).

These tests parse the checked-in YAML (and, for banned-command checks, the
raw text) rather than re-deriving the file's own prose, so a real scope
regression -- an added ``docs/**`` glob, a stray ``kosha ingest`` step, or a
flipped review-queue auto-approval -- fails a test here instead of shipping.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from kosha.sync.cli_reference import CLI_REFERENCE_PATH, README_PATH
from kosha.sync.state import SYNC_STATE_RELATIVE_PATH
from kosha.sync.status_surfaces import GATE0_STATUS_PATH
from kosha.sync.traversal import FALLBACK_FRAGMENT_PATH, FALLBACK_SKILL_PATH, MCP_DOC_PATH

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_RELATIVE_PATH = Path("docs/examples/kosha-sync-pr.yml")
WORKFLOW_PATH = REPO_ROOT / WORKFLOW_RELATIVE_PATH

# The exact set of generated public surfaces the M2-M5 sync checkers own
# (docs/cli-reference.md + README's CLI table, docs/gate0-status.md +
# README's acceptance table, docs/mcp-integration.md, the two consumer/
# fallback artifacts, and the sync-state marker). Deriving this from the
# checkers' own path constants -- instead of a second hardcoded literal
# list -- means a checker's path changing without the workflow following
# fails here too, not just a typo in the workflow's own path list.
EXPECTED_GENERATED_SURFACE_PATHS = {
    str(README_PATH),
    str(CLI_REFERENCE_PATH),
    str(GATE0_STATUS_PATH),
    str(MCP_DOC_PATH),
    str(FALLBACK_FRAGMENT_PATH),
    str(FALLBACK_SKILL_PATH),
    str(SYNC_STATE_RELATIVE_PATH),
}

BANNED_BROAD_OR_UNRELATED_PATHS = (
    "docs/**",
    "docs/*",
    "docs/",
    "bundles/**",
    "bundles/*",
    "bundles/",
    "tests/**",
    "tests/*",
    "tests/",
    "src/**",
    "src/*",
    "src/",
    "AGENTS.md",
    "CLAUDE.md",
)


def _raw_text() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def _load_workflow() -> dict[Any, Any]:
    loaded = yaml.safe_load(_raw_text())
    assert isinstance(loaded, dict)
    return loaded


def _triggers(workflow: dict[Any, Any]) -> dict[Any, Any]:
    # PyYAML's SafeLoader resolves the unquoted YAML 1.1 scalar `on` to the
    # boolean True, so the trigger map is keyed by True, not the string "on".
    triggers = workflow[True] if True in workflow else workflow["on"]
    assert isinstance(triggers, dict)
    return triggers


def _only_job_steps(workflow: dict[Any, Any]) -> list[dict[Any, Any]]:
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict) and len(jobs) == 1, "expected exactly one job"
    (job,) = jobs.values()
    steps = job["steps"]
    assert isinstance(steps, list) and steps
    return steps


def _run_scripts(workflow: dict[Any, Any]) -> list[str]:
    return [step["run"] for step in _only_job_steps(workflow) if "run" in step]


def _create_pull_request_step(workflow: dict[Any, Any]) -> dict[Any, Any]:
    matches = [
        step
        for step in _only_job_steps(workflow)
        if str(step.get("uses", "")).startswith("peter-evans/create-pull-request")
    ]
    assert len(matches) == 1, "expected exactly one peter-evans/create-pull-request step"
    return matches[0]


def _add_paths(workflow: dict[Any, Any]) -> set[str]:
    raw = _create_pull_request_step(workflow)["with"]["add-paths"]
    assert isinstance(raw, str)
    return {line.strip() for line in raw.splitlines() if line.strip()}


def _executable_step_text(workflow: dict[Any, Any]) -> str:
    """The operationally meaningful parts of every step: ``run`` scripts,
    ``uses`` action refs, and ``with`` inputs -- excluding the free-form
    ``body`` markdown field, which is human-facing PR description prose,
    not something that executes. Safety checks for banned *commands* must
    only look here, so a documentation sentence disclaiming a command
    (e.g. "does not run `kosha ingest`") can't itself trip the check.
    """
    parts: list[str] = []
    for step in _only_job_steps(workflow):
        if "run" in step:
            parts.append(step["run"])
        if "uses" in step:
            parts.append(step["uses"])
        with_block = step.get("with")
        if isinstance(with_block, dict):
            parts.extend(str(value) for key, value in with_block.items() if key != "body")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Location: documentation-only example, never a registered live workflow.
# ---------------------------------------------------------------------------


def test_workflow_example_lives_under_docs_examples() -> None:
    assert WORKFLOW_PATH.is_file()
    assert WORKFLOW_PATH.parent == REPO_ROOT / "docs" / "examples"


def test_workflow_example_is_not_registered_as_a_live_github_workflow() -> None:
    live_workflow_dir = REPO_ROOT / ".github" / "workflows"
    live_names = {path.name for path in live_workflow_dir.glob("*.yml")}
    assert WORKFLOW_PATH.name not in live_names


# ---------------------------------------------------------------------------
# Copyability: schedule + workflow_dispatch triggers so a maintainer can
# both let it run unattended and fire it on demand once copied in.
# ---------------------------------------------------------------------------


def test_workflow_triggers_on_schedule_with_a_cron_expression() -> None:
    triggers = _triggers(_load_workflow())
    assert "schedule" in triggers
    schedule = triggers["schedule"]
    assert isinstance(schedule, list) and schedule
    assert all("cron" in entry and entry["cron"] for entry in schedule)


def test_workflow_also_supports_manual_workflow_dispatch() -> None:
    triggers = _triggers(_load_workflow())
    assert "workflow_dispatch" in triggers


# ---------------------------------------------------------------------------
# Executed commands: only the read/write-generated-surface + diagnostic
# commands, never a bundle-mutating ingest.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "expected_command",
    [
        "uv run kosha sync docs",
        "uv run kosha sync status",
        "uv run kosha sync check",
        "uv run kosha doctor providers",
    ],
)
def test_workflow_runs_expected_sync_and_doctor_commands(expected_command: str) -> None:
    scripts = "\n".join(_run_scripts(_load_workflow()))
    assert expected_command in scripts


def test_workflow_never_runs_kosha_ingest() -> None:
    assert "kosha ingest" not in _executable_step_text(_load_workflow())


def test_workflow_never_passes_an_unattended_yes_flag() -> None:
    assert "--yes" not in _executable_step_text(_load_workflow())


def test_workflow_never_touches_the_block_lane_review_queue() -> None:
    # `kosha review-queue decide <queue> <item> approve --reviewer ...` is the
    # real CLI command that records a BLOCK-lane approval; its absence here
    # means this workflow structurally cannot execute one.
    text = _executable_step_text(_load_workflow())
    assert "review-queue decide" not in text
    assert "review-queue" not in text


# ---------------------------------------------------------------------------
# BLOCK-lane / approval language: the workflow's PR body is allowed (and
# expected) to *disclaim* approval in prose ("does not approve BLOCK-lane
# knowledge changes"). What must never appear is an un-negated, positive
# claim of approval -- that would mean the safety disclosure was weakened
# or dropped in favor of language describing real auto-approval behavior.
# ---------------------------------------------------------------------------


def test_workflow_discloses_that_it_does_not_approve_block_lane_changes() -> None:
    assert re.search(r"does not approve block-lane", _raw_text(), flags=re.IGNORECASE)


def test_every_mention_of_approval_is_negated_never_a_positive_claim() -> None:
    text = _raw_text()
    matches = list(re.finditer(r"approve", text, flags=re.IGNORECASE))
    assert matches, "expected the BLOCK-lane non-approval disclosure to be present"
    for match in matches:
        preceding = text[max(0, match.start() - 12) : match.start()]
        message = (
            "found un-negated approval language: "
            f"{text[max(0, match.start() - 40):match.start() + 40]!r}"
        )
        assert re.search(r"does not\s*$", preceding, flags=re.IGNORECASE), message


def test_workflow_never_claims_automatic_or_auto_approval() -> None:
    lowered = _raw_text().lower()
    assert "auto-approv" not in lowered
    assert "automatically approv" not in lowered


# ---------------------------------------------------------------------------
# Bundle safety: the PR body may disclaim mutating OKF bundles, but no
# `bundles/` path may ever be staged for the PR.
# ---------------------------------------------------------------------------


def test_workflow_never_stages_a_bundles_directory_path() -> None:
    assert "bundles/" not in _executable_step_text(_load_workflow())


# ---------------------------------------------------------------------------
# PR mechanism + scope: peter-evans/create-pull-request, add-paths pinned to
# exactly the generated public surfaces (never a broader tree).
# ---------------------------------------------------------------------------


def test_workflow_opens_its_pull_request_via_create_pull_request_action() -> None:
    step = _create_pull_request_step(_load_workflow())
    assert re.match(r"^peter-evans/create-pull-request@v\d+", step["uses"])


def test_workflow_add_paths_scoped_exactly_to_generated_public_surfaces() -> None:
    assert _add_paths(_load_workflow()) == EXPECTED_GENERATED_SURFACE_PATHS


@pytest.mark.parametrize("banned_path", BANNED_BROAD_OR_UNRELATED_PATHS)
def test_workflow_add_paths_excludes_broad_or_unrelated_trees(banned_path: str) -> None:
    assert banned_path not in _add_paths(_load_workflow())
