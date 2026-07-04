"""Git store: branch-per-ingest, commit-per-plan, daily backup tag (M10 PR-1)."""

from __future__ import annotations

import subprocess
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


def test_tags_matching_filters_by_prefix(tmp_path: Path) -> None:
    store, _ = _seeded_repo(tmp_path)
    store.tag_daily_backup(date(2026, 6, 28))
    store.tag_daily_backup(date(2026, 6, 29))
    subprocess.run(["git", "-C", str(tmp_path), "tag", "release/v1"], check=True)
    assert store.tags_matching("backup/") == ["backup/2026-06-28", "backup/2026-06-29"]
    assert store.tags_matching("release/") == ["release/v1"]


def test_diff_name_status_reports_added_modified_and_deleted(tmp_path: Path) -> None:
    store, _ = _seeded_repo(tmp_path)
    tag = store.tag_daily_backup(date(2026, 6, 28))  # snapshot: README.md only

    (tmp_path / "README.md").write_text("changed\n", encoding="utf-8")
    (tmp_path / "new.md").write_text("new\n", encoding="utf-8")
    store.commit(["README.md", "new.md"], "feat: change and add")

    # Restoring HEAD -> tag would modify README.md and delete new.md.
    status_by_path = {path: status for status, path in store.diff_name_status("HEAD", tag)}
    assert status_by_path["README.md"] == "M"
    assert status_by_path["new.md"] == "D"


def test_restore_tree_and_commit_staged_reverts_to_the_tagged_tree(tmp_path: Path) -> None:
    store, _ = _seeded_repo(tmp_path)
    tag = store.tag_daily_backup(date(2026, 6, 28))

    (tmp_path / "README.md").write_text("changed\n", encoding="utf-8")
    (tmp_path / "new.md").write_text("new\n", encoding="utf-8")
    store.commit(["README.md", "new.md"], "feat: change and add")

    store.create_branch("recovery/restore-test")
    store.restore_tree(tag)
    sha = store.commit_staged("chore(recovery): restore from backup/2026-06-28")

    assert sha == store.current_sha("HEAD")
    assert store.show("HEAD", "README.md") == "seed"  # _git() strips trailing whitespace
    assert "new.md" not in store.tracked_files("HEAD")
    assert store.tracked_files("HEAD") == store.tracked_files(tag)
