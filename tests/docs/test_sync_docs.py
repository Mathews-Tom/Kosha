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
from kosha.sync.public_claims import find_banned_claims, normalize_claim_line, public_doc_paths
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


# ---------------------------------------------------------------------------
# M6 PR-2: docs/sync.md is the sync operations guide the workflow example
# points operators at. It must document the full command boundary (all four
# `sync` subcommands plus validate/ingest/serve/doctor providers), point back
# at the scheduled workflow example above, restate the same no-ingest/
# no-bundle-mutation/no-auto-approval guarantees the workflow enforces
# structurally, and stay inside the M1 public-claim boundary the sync
# checker polices.
# ---------------------------------------------------------------------------

GUIDE_RELATIVE_PATH = Path("docs/sync.md")
GUIDE_PATH = REPO_ROOT / GUIDE_RELATIVE_PATH

GUIDE_DOCUMENTED_COMMANDS = (
    "kosha sync check",
    "kosha sync docs",
    "kosha sync status",
    "kosha sync agent-fragment",
    "kosha validate",
    "kosha ingest",
    "kosha serve",
    "kosha doctor providers",
)


def _guide_text() -> str:
    return GUIDE_PATH.read_text(encoding="utf-8")


def _guide_normalized_text() -> str:
    # Strip markdown emphasis/code markers the same way the public-claim
    # scanner does, so a formatting-only change (dropping backticks, adding
    # bold) never breaks a content assertion below.
    return "\n".join(normalize_claim_line(line) for line in _guide_text().splitlines())


def test_sync_guide_exists_directly_under_docs() -> None:
    assert GUIDE_PATH.is_file()
    assert GUIDE_PATH.parent == REPO_ROOT / "docs"


@pytest.mark.parametrize("command", GUIDE_DOCUMENTED_COMMANDS)
def test_sync_guide_documents_every_command_in_the_boundary(command: str) -> None:
    assert command in _guide_normalized_text()


def test_sync_guide_references_the_scheduled_workflow_example() -> None:
    assert str(WORKFLOW_RELATIVE_PATH) in _guide_text()


# ---------------------------------------------------------------------------
# Scope guarantees: the guide must keep asserting the boundaries the
# workflow example enforces structurally, so a reader can't come away
# believing scheduled sync mutates bundles or grants approval.
# ---------------------------------------------------------------------------


def test_sync_guide_states_sync_is_not_an_ingest_workflow() -> None:
    assert re.search(r"not an ingest workflow", _guide_normalized_text(), flags=re.IGNORECASE)


def test_sync_guide_states_sync_does_not_change_an_okf_bundle() -> None:
    assert re.search(
        r"does not change an okf bundle",
        _guide_normalized_text(),
        flags=re.IGNORECASE,
    )


def test_sync_guide_states_scheduled_sync_does_not_run_ingest() -> None:
    assert re.search(r"does not run kosha ingest", _guide_normalized_text(), flags=re.IGNORECASE)


def test_sync_guide_states_scheduled_sync_does_not_pass_yes() -> None:
    assert re.search(r"does not pass --yes", _guide_normalized_text(), flags=re.IGNORECASE)


def test_sync_guide_states_scheduled_sync_does_not_stage_bundle_paths() -> None:
    assert re.search(r"does not stage bundle paths", _guide_normalized_text(), flags=re.IGNORECASE)


def test_sync_guide_never_directs_staging_the_bundles_directory() -> None:
    assert "bundles/" not in _guide_text()


def test_sync_guide_states_scheduled_sync_does_not_approve_block_lane_changes() -> None:
    assert re.search(r"does not approve block-lane", _guide_normalized_text(), flags=re.IGNORECASE)


def test_sync_guide_states_scheduled_workflows_must_not_approve_block_lane_changes() -> None:
    assert re.search(r"must not approve block-lane", _guide_normalized_text(), flags=re.IGNORECASE)


def test_sync_guide_never_claims_automatic_or_auto_approval() -> None:
    lowered = _guide_text().lower()
    assert "auto-approv" not in lowered
    assert "automatically approv" not in lowered


# ---------------------------------------------------------------------------
# Public-claim boundary: docs/sync.md is new prose under docs/ and must stay
# inside the corpus the M1 scanner polices, both by remaining discoverable
# and by carrying no banned claim itself.
# ---------------------------------------------------------------------------


def test_sync_guide_is_included_in_the_scanned_public_claim_corpus() -> None:
    assert GUIDE_PATH in public_doc_paths(REPO_ROOT)


def test_sync_guide_has_no_banned_public_claims() -> None:
    violations = find_banned_claims(_guide_text())
    assert not violations, f"banned public claim(s) in {GUIDE_RELATIVE_PATH}: {violations}"


# ---------------------------------------------------------------------------
# M6 PR-3: docs/docs-impact-policy.md is the gate for future agent-authored
# docs prose. It must state the impact-plan table's source-change ->
# affected-document -> required-edit -> evidence -> mode concept, the
# deterministic-or-agent-authored chain, block broad rewrites,
# formatting-only edits, unsupported public/real-model claims, an
# unhalted-M14+ claim, a sandboxed-filesystem claim, `kosha ingest --yes`,
# scheduled-sync bundle staging, and BLOCK-lane approval, and list the full
# required-checks command boundary -- including this file's own targeted
# test command.
# ---------------------------------------------------------------------------

POLICY_RELATIVE_PATH = Path("docs/docs-impact-policy.md")
POLICY_PATH = REPO_ROOT / POLICY_RELATIVE_PATH

POLICY_IMPACT_PLAN_CHAIN = (
    "source change -> affected document -> required edit -> evidence -> "
    "deterministic or agent-authored"
)

POLICY_IMPACT_PLAN_COLUMNS = (
    "Source change",
    "Affected document",
    "Required edit",
    "Evidence",
    "Mode",
)

# Every phrase below is a substring of one "Blocked changes" bullet in the
# policy (normalized + lowercased), so a dropped rule -- not just a dropped
# bullet marker -- fails the matching test.
POLICY_BLOCKED_RULES = (
    "broad rewrites",
    "formatting-only edits",
    "public claims without source evidence",
    "real-model quality unless backed by a checked-in recorded report",
    "m14+ product expansion is unhalted without a new recorded go decision",
    "host sessions with generic filesystem tools are sandboxed by kosha today",
    "kosha ingest --yes",
    "stages bundle files from scheduled sync",
    "approves block-lane knowledge changes",
)

POLICY_REQUIRED_CHECKS = (
    "uv run pytest tests/docs/test_sync_docs.py tests/docs/test_public_claims.py -q",
    "uv run kosha sync check",
    "uv run kosha doctor providers",
    "uv run ruff check",
    "uv run mypy --strict src",
    "uv run pytest -q",
    "uv run kosha validate tests/fixtures/good_bundle",
)


def _policy_text() -> str:
    return POLICY_PATH.read_text(encoding="utf-8")


def _policy_normalized_text() -> str:
    return "\n".join(normalize_claim_line(line) for line in _policy_text().splitlines())


def test_docs_impact_policy_exists_directly_under_docs() -> None:
    assert POLICY_PATH.is_file()
    assert POLICY_PATH.parent == REPO_ROOT / "docs"


@pytest.mark.parametrize("column", POLICY_IMPACT_PLAN_COLUMNS)
def test_docs_impact_policy_impact_plan_names_every_required_column(column: str) -> None:
    assert column in _policy_normalized_text()


def test_docs_impact_policy_impact_plan_row_names_both_modes() -> None:
    normalized = _policy_normalized_text()
    assert "deterministic" in normalized
    assert "agent-authored" in normalized


def test_docs_impact_policy_states_the_deterministic_or_agent_authored_chain() -> None:
    # The literal chain lives in a fenced ```text block (no markdown emphasis
    # or code-span markers to strip), so the raw text is the right window.
    assert POLICY_IMPACT_PLAN_CHAIN in _policy_text()


@pytest.mark.parametrize("blocked_rule", POLICY_BLOCKED_RULES)
def test_docs_impact_policy_blocks_required_rule(blocked_rule: str) -> None:
    assert blocked_rule in _policy_normalized_text().lower()


@pytest.mark.parametrize("required_check", POLICY_REQUIRED_CHECKS)
def test_docs_impact_policy_lists_required_check(required_check: str) -> None:
    assert required_check in _policy_text()


# ---------------------------------------------------------------------------
# Public-claim boundary: docs/docs-impact-policy.md is new prose under docs/
# and must stay inside the corpus the M1 scanner polices, both by remaining
# discoverable and by carrying no banned claim itself.
# ---------------------------------------------------------------------------


def test_docs_impact_policy_is_included_in_the_scanned_public_claim_corpus() -> None:
    assert POLICY_PATH in public_doc_paths(REPO_ROOT)


def test_docs_impact_policy_has_no_banned_public_claims() -> None:
    violations = find_banned_claims(_policy_text())
    assert not violations, f"banned public claim(s) in {POLICY_RELATIVE_PATH}: {violations}"


# ---------------------------------------------------------------------------
# Final references: README's documentation index and docs/sync.md must both
# stay wired to the new policy, so a reader following either path finds it.
# Matching only the parenthesized link target (not the link text or the
# surrounding table-row prose) keeps this from breaking on a harmless
# wording tweak while still failing the moment the wiring itself drops.
# ---------------------------------------------------------------------------


def _readme_text() -> str:
    return (REPO_ROOT / README_PATH).read_text(encoding="utf-8")


def test_readme_documentation_index_links_the_sync_guide() -> None:
    assert "(docs/sync.md)" in _readme_text()


def test_readme_documentation_index_links_the_docs_impact_policy() -> None:
    assert "(docs/docs-impact-policy.md)" in _readme_text()


def test_sync_guide_links_to_the_docs_impact_policy() -> None:
    assert "(docs-impact-policy.md)" in _guide_text()
