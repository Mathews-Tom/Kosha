"""Structural checks for the packaged ``kosha validate`` GitHub Action (M8 PR-2).

The action installs from PyPI at runtime, so it cannot be exercised end-to-end
by the unit test suite (that is what ``.github/workflows/action-smoke.yml``
does, live, on every push). These tests catch the cheaper, deterministic
failure mode instead: a malformed or drifted ``action.yml``/workflow fixture.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
ACTION_YAML = ROOT / "action.yml"
SMOKE_WORKFLOW = ROOT / ".github" / "workflows" / "action-smoke.yml"


def _load(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return result


def test_action_yaml_declares_a_composite_action_with_bundle_path() -> None:
    action = _load(ACTION_YAML)
    assert action["runs"]["using"] == "composite"
    assert "bundle-path" in action["inputs"]
    assert action["inputs"]["bundle-path"]["required"] is True
    assert "version" in action["inputs"]
    assert action["inputs"]["version"]["required"] is False


def test_action_yaml_invokes_kosha_validate_with_the_bundle_path_input() -> None:
    action = _load(ACTION_YAML)
    steps = action["runs"]["steps"]
    run_steps = [step for step in steps if "run" in step]
    assert run_steps, "expected at least one run step invoking kosha validate"
    assert any("kosha validate" in step["run"] for step in run_steps)
    assert any("${{ inputs.bundle-path }}" in step["run"] for step in run_steps)


def test_action_yaml_pins_setup_uv_to_a_specific_version() -> None:
    action = _load(ACTION_YAML)
    uses_steps = [step["uses"] for step in action["runs"]["steps"] if "uses" in step]
    assert any(use.startswith("astral-sh/setup-uv@") for use in uses_steps)
    assert not any(use == "astral-sh/setup-uv" for use in uses_steps)


def test_smoke_workflow_exercises_the_local_action_against_both_fixtures() -> None:
    workflow = _load(SMOKE_WORKFLOW)
    steps = workflow["jobs"]["smoke"]["steps"]
    action_steps = [step for step in steps if step.get("uses") == "./"]
    assert len(action_steps) == 2
    bundle_paths = {step["with"]["bundle-path"] for step in action_steps}
    assert bundle_paths == {"tests/fixtures/good_bundle", "tests/fixtures/bad_bundle"}
    # The non-conformant run must be allowed to fail so the workflow can assert
    # on its outcome instead of the job aborting outright.
    bad_step = next(
        step for step in action_steps if step["with"]["bundle-path"] == "tests/fixtures/bad_bundle"
    )
    assert bad_step.get("continue-on-error") is True


def test_smoke_workflow_asserts_the_bad_bundle_run_actually_failed() -> None:
    workflow = _load(SMOKE_WORKFLOW)
    steps = workflow["jobs"]["smoke"]["steps"]
    assertion_step = steps[-1]
    assert "exit 1" in assertion_step["run"]
    assert assertion_step.get("if") == "steps.bad.outcome != 'failure'"


def test_referenced_fixture_bundles_exist() -> None:
    assert (ROOT / "tests" / "fixtures" / "good_bundle").is_dir()
    assert (ROOT / "tests" / "fixtures" / "bad_bundle").is_dir()
