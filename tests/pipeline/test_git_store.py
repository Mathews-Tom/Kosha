"""Git store: branch-per-ingest, commit-per-plan, daily backup tag (M10 PR-1)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from kosha.git_store import GitError, GitStore


def _seeded_repo(tmp_path: Path) -> tuple[GitStore, str]:
    """Init a repo with one commit on ``main``; return the store and main's SHA."""
    store = GitStore.init(tmp_path)
    (tmp_path / "README.md").write_text("seed\n", encoding="utf-8")
    store.commit(["README.md"], "chore: seed")
    return store, store.current_sha("main")


def test_init_creates_repo_on_main(tmp_path: Path) -> None:
    store = GitStore.init(tmp_path)
    assert store.is_repo()
    assert store.head_branch() == "main"


def test_branch_per_ingest_keeps_main_off_the_write_path(tmp_path: Path) -> None:
    store, main_sha = _seeded_repo(tmp_path)

    store.create_branch("ingest/policy-update")
    (tmp_path / "policies").mkdir()
    (tmp_path / "policies" / "returns.md").write_text("returns\n", encoding="utf-8")
    store.commit(["policies/returns.md"], "feat: update returns")

    assert store.head_branch() == "ingest/policy-update"
    assert store.branch_exists("ingest/policy-update")
    assert "policies/returns.md" in store.tracked_files()
    # Nothing reaches main without a merge: its tree and ref are unchanged.
    assert "policies/returns.md" not in store.tracked_files("main")
    assert store.current_sha("main") == main_sha


def test_commit_returns_sha_and_message(tmp_path: Path) -> None:
    store, _ = _seeded_repo(tmp_path)
    store.create_branch("ingest/x")
    (tmp_path / "a.md").write_text("a\n", encoding="utf-8")
    sha = store.commit(["a.md"], "feat: add a")
    assert sha == store.current_sha("HEAD")
    assert store.commit_message() == "feat: add a"


def test_daily_backup_tag_is_one_per_day_and_force_moves(tmp_path: Path) -> None:
    store, _ = _seeded_repo(tmp_path)
    on = date(2026, 6, 28)

    name = store.tag_daily_backup(on)
    assert name == "backup/2026-06-28"
    assert store.tag_exists(name)
    assert store.current_sha(name) == store.current_sha("HEAD")

    (tmp_path / "b.md").write_text("b\n", encoding="utf-8")
    store.commit(["b.md"], "feat: add b")
    moved = store.tag_daily_backup(on)
    assert moved == name  # same day → same tag
    assert store.current_sha(name) == store.current_sha("HEAD")  # force-moved to new HEAD


def test_commit_with_no_paths_fails_loud(tmp_path: Path) -> None:
    store, _ = _seeded_repo(tmp_path)
    with pytest.raises(GitError):
        store.commit([], "noop")


def test_failed_git_invocation_raises(tmp_path: Path) -> None:
    store, _ = _seeded_repo(tmp_path)
    with pytest.raises(GitError):
        store.switch("no-such-branch")
