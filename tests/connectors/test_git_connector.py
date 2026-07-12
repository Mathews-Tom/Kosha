"""Bounded Git repository evidence connector (DEVELOPMENT_PLAN.md M7)."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from kosha.connectors.config import GIT_CONNECTOR
from kosha.connectors.git import GitConnectorError, _require_within_allowed_roots, run_git_source
from kosha.connectors.model import ConnectorRunContext, SourceInstance, SourceRunOutcome
from kosha.connectors.run import run_source_instance
from kosha.connectors.state import ConnectorStateStore
from kosha.evidence import EvidenceStore, evidence_root
from kosha.git_store import GitStore

_ASOF = datetime(2026, 6, 28, tzinfo=UTC)


def _seed_bundle(tmp_path: Path) -> Path:
    bundle = tmp_path / "bundle"
    (bundle / "policies").mkdir(parents=True)
    (bundle / "policies" / "returns.md").write_text(
        "---\ntype: policy\ntitle: Returns\n"
        "description: When and how customers may return products.\n---\n"
        "Standard returns are accepted within 30 days of delivery.\n",
        encoding="utf-8",
    )
    GitStore.init(bundle).commit(["policies/returns.md"], "chore: seed")
    return bundle


def _seed_source_repo(tmp_path: Path, *, name: str = "source-repo") -> tuple[Path, GitStore]:
    repo = tmp_path / name
    store = GitStore.init(repo, default_branch="main")
    (repo / "notes.md").write_text(
        "---\ntype: policy\ntitle: Notes\ndescription: Working notes.\n---\n"
        "The team tracks open questions here for later triage.\n",
        encoding="utf-8",
    )
    store.commit(["notes.md"], "chore: initial notes")
    return repo, store


def _instance(instance_id: str, repo: Path, **config: str) -> SourceInstance:
    return SourceInstance(
        instance_id=instance_id, connector_id="git", config={"path": str(repo), **config}
    )


def _allow_root(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    monkeypatch.setenv("KOSHA_GIT_ALLOWED_ROOTS", str(root))


def _dry_run_ctx(
    instance: SourceInstance, bundle: Path, *, cursor: str | None = None
) -> ConnectorRunContext:
    return ConnectorRunContext(
        instance=instance,
        bundle_root=bundle,
        asof=_ASOF,
        cursor=cursor,
        evidence_store=EvidenceStore(evidence_root(bundle)),
        dry_run=True,
        assume_yes=True,
        reviewer=None,
        reader=None,
    )


# --- registry shape ----------------------------------------------------------


def test_the_git_connector_is_registered_with_a_cursor_and_required_env_var() -> None:
    assert GIT_CONNECTOR.connector_id == "git"
    assert GIT_CONNECTOR.required_config_keys == ("path",)
    assert GIT_CONNECTOR.required_env_vars == ("KOSHA_GIT_ALLOWED_ROOTS",)
    assert GIT_CONNECTOR.supports_cursor is True


# --- path containment ---------------------------------------------------------


def test_a_path_outside_every_allowed_root_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _ = _seed_source_repo(tmp_path)
    allowed = tmp_path / "elsewhere"
    allowed.mkdir()
    _allow_root(monkeypatch, allowed)
    with pytest.raises(GitConnectorError, match="outside every KOSHA_GIT_ALLOWED_ROOTS"):
        _require_within_allowed_roots(repo.resolve())


def test_a_path_inside_an_allowed_root_is_accepted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _ = _seed_source_repo(tmp_path)
    _allow_root(monkeypatch, tmp_path)
    _require_within_allowed_roots(repo.resolve())  # does not raise


def test_a_missing_allowed_roots_env_var_fails_loud(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _ = _seed_source_repo(tmp_path)
    monkeypatch.delenv("KOSHA_GIT_ALLOWED_ROOTS", raising=False)
    with pytest.raises(GitConnectorError, match="KOSHA_GIT_ALLOWED_ROOTS is not set"):
        _require_within_allowed_roots(repo.resolve())


def test_source_run_rejects_a_path_escaping_allowed_roots_and_advances_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _seed_bundle(tmp_path)
    repo, _ = _seed_source_repo(tmp_path)
    other_root = tmp_path / "other"
    other_root.mkdir()
    _allow_root(monkeypatch, other_root)
    state_store = ConnectorStateStore(tmp_path / "state")
    report = run_source_instance(
        _instance("repo", repo),
        bundle_root=bundle,
        state_store=state_store,
        asof=_ASOF,
        assume_yes=True,
    )
    assert report.outcome is SourceRunOutcome.FAILED
    assert "outside every KOSHA_GIT_ALLOWED_ROOTS" in report.message
    assert report.state.cursor is None


# --- initial snapshot / incremental window ------------------------------------


def test_initial_run_commits_a_bounded_snapshot_and_advances_cursor_to_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _seed_bundle(tmp_path)
    repo, store = _seed_source_repo(tmp_path)
    _allow_root(monkeypatch, tmp_path)
    state_store = ConnectorStateStore(tmp_path / "state")
    report = run_source_instance(
        _instance("repo", repo),
        bundle_root=bundle,
        state_store=state_store,
        asof=_ASOF,
        assume_yes=True,
    )
    assert report.outcome is SourceRunOutcome.SUCCESS
    assert report.state.cursor == store.current_sha()


def test_an_incremental_run_windows_since_the_prior_cursor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _seed_bundle(tmp_path)
    repo, store = _seed_source_repo(tmp_path)
    _allow_root(monkeypatch, tmp_path)
    state_store = ConnectorStateStore(tmp_path / "state")
    instance = _instance("repo", repo)

    first = run_source_instance(
        instance, bundle_root=bundle, state_store=state_store, asof=_ASOF, assume_yes=True
    )
    assert first.outcome is SourceRunOutcome.SUCCESS
    first_sha = first.state.cursor

    (repo / "notes.md").write_text(
        "---\ntype: policy\ntitle: Notes\ndescription: Working notes.\n---\n"
        "A second question was added to the running list.\n",
        encoding="utf-8",
    )
    store.commit(["notes.md"], "chore: second notes")
    second_sha = store.current_sha()

    second = run_source_instance(
        instance,
        bundle_root=bundle,
        state_store=state_store,
        asof=_ASOF + timedelta(hours=1),
        assume_yes=True,
    )
    assert second.outcome is SourceRunOutcome.SUCCESS
    assert second.state.cursor == second_sha
    assert second.state.cursor != first_sha
    assert second.ingest_result is not None
    assert second.ingest_result.evidence_run is not None
    coverage = second.ingest_result.evidence_run.run.coverage
    assert coverage.cursor_before == first_sha
    assert coverage.cursor_after == second_sha
    text = next(iter(second.ingest_result.evidence_run.texts.values()))
    assert f"Commits since {first_sha}: 1 of 1" in text
    assert "chore: second notes" in text
    assert "chore: initial notes" not in text  # window excludes the already-seen commit


# --- rewritten / missing cursor -----------------------------------------------


def test_a_cursor_no_longer_reachable_from_head_fails_loud_and_preserves_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _seed_bundle(tmp_path)
    repo, store = _seed_source_repo(tmp_path)
    _allow_root(monkeypatch, tmp_path)
    state_store = ConnectorStateStore(tmp_path / "state")
    instance = _instance("repo", repo)

    first = run_source_instance(
        instance, bundle_root=bundle, state_store=state_store, asof=_ASOF, assume_yes=True
    )
    assert first.outcome is SourceRunOutcome.SUCCESS
    prior_cursor = first.state.cursor

    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "--amend",
            "-m",
            "chore: rewritten history",
        ],
        check=True,
        capture_output=True,
    )
    rewritten_sha = store.current_sha()
    assert rewritten_sha != prior_cursor

    second = run_source_instance(
        instance, bundle_root=bundle, state_store=state_store, asof=_ASOF, assume_yes=True
    )
    assert second.outcome is SourceRunOutcome.FAILED
    assert "no longer an ancestor" in second.message
    assert second.state.cursor == prior_cursor


# --- dirty-tree opt-in ---------------------------------------------------------


def test_dirty_working_tree_is_excluded_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _seed_bundle(tmp_path)
    repo, _ = _seed_source_repo(tmp_path)
    (repo / "scratch.md").write_text("uncommitted scratch content\n", encoding="utf-8")
    _allow_root(monkeypatch, tmp_path)

    result = run_git_source(_dry_run_ctx(_instance("repo", repo), bundle))
    assert result.evidence_run is not None
    text = next(iter(result.evidence_run.texts.values()))
    assert "scratch.md" not in text
    assert "Working tree status" not in text


def test_dirty_working_tree_is_included_when_explicitly_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _seed_bundle(tmp_path)
    repo, _ = _seed_source_repo(tmp_path)
    (repo / "scratch.md").write_text("uncommitted scratch content\n", encoding="utf-8")
    _allow_root(monkeypatch, tmp_path)

    instance = _instance("repo", repo, include_dirty="true")
    result = run_git_source(_dry_run_ctx(instance, bundle))
    assert result.evidence_run is not None
    text = next(iter(result.evidence_run.texts.values()))
    assert "scratch.md" in text
    assert "Working tree status (dirty, opt-in)" in text


# --- configured branch label wins over the checked-out branch ------------------


def test_evidence_labels_the_configured_branch_not_the_checked_out_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _seed_bundle(tmp_path)
    repo, store = _seed_source_repo(tmp_path)
    _allow_root(monkeypatch, tmp_path)
    store.create_branch("scratch")  # switches the working tree off of "main"

    instance = _instance("repo", repo, branch="main")
    result = run_git_source(_dry_run_ctx(instance, bundle))
    assert result.evidence_run is not None
    text = next(iter(result.evidence_run.texts.values()))
    assert "Branch: main" in text
    assert "Branch: scratch" not in text


# --- deterministic evidence for a fixed repository state -----------------------


def test_evidence_is_byte_identical_for_a_fixed_repository_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _seed_bundle(tmp_path)
    repo, _ = _seed_source_repo(tmp_path)
    _allow_root(monkeypatch, tmp_path)
    instance = _instance("repo", repo)

    first = run_git_source(_dry_run_ctx(instance, bundle))
    second = run_git_source(_dry_run_ctx(instance, bundle))
    assert first.evidence_run is not None and second.evidence_run is not None
    first_digests = {doc.sha256 for doc in first.evidence_run.run.evidence}
    second_digests = {doc.sha256 for doc in second.evidence_run.run.evidence}
    assert first_digests == second_digests
    assert first_digests  # not empty: the seed commit produced evidence


# --- malformed config fails loud ------------------------------------------------


def test_a_non_boolean_include_dirty_value_fails_loud(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _seed_bundle(tmp_path)
    repo, _ = _seed_source_repo(tmp_path)
    _allow_root(monkeypatch, tmp_path)
    state_store = ConnectorStateStore(tmp_path / "state")
    instance = _instance("repo", repo, include_dirty="maybe")
    report = run_source_instance(
        instance, bundle_root=bundle, state_store=state_store, asof=_ASOF, assume_yes=True
    )
    assert report.outcome is SourceRunOutcome.FAILED
    assert "include_dirty must be a boolean" in report.message


def test_a_non_directory_path_fails_loud(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _seed_bundle(tmp_path)
    _allow_root(monkeypatch, tmp_path)
    state_store = ConnectorStateStore(tmp_path / "state")
    instance = _instance("repo", tmp_path / "does-not-exist")
    report = run_source_instance(
        instance, bundle_root=bundle, state_store=state_store, asof=_ASOF, assume_yes=True
    )
    assert report.outcome is SourceRunOutcome.FAILED
    assert "not a directory" in report.message


def test_a_non_git_directory_fails_loud(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _seed_bundle(tmp_path)
    plain_dir = tmp_path / "plain"
    plain_dir.mkdir()
    _allow_root(monkeypatch, tmp_path)
    state_store = ConnectorStateStore(tmp_path / "state")
    instance = _instance("repo", plain_dir)
    report = run_source_instance(
        instance, bundle_root=bundle, state_store=state_store, asof=_ASOF, assume_yes=True
    )
    assert report.outcome is SourceRunOutcome.FAILED
    assert "not a git repository" in report.message
