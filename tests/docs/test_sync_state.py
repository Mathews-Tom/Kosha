"""Sync state and no-op foundation tests."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from kosha.sync import (
    InvalidSyncStateError,
    ProviderState,
    SnapshotError,
    SyncDecisionError,
    SyncDecisionReason,
    SyncState,
    content_snapshot,
    current_git_head,
    decide_sync,
    load_sync_state,
    save_sync_state,
    sync_state_path,
)


def test_sync_state_round_trips_stable_json(tmp_path: Path) -> None:
    path = sync_state_path(tmp_path)
    state = SyncState(
        updated_at="2026-07-07T00:00:00+00:00",
        command="sync-docs",
        git_head="abc123",
        kosha_version="0.1.0",
        content_snapshot="content-sha",
        source_snapshot="source-sha",
        providers=ProviderState(embedding="lexical-hash-256", generation="extractive-3"),
    )

    save_sync_state(path, state)

    assert load_sync_state(path) == state
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "command": "sync-docs",
        "contentSnapshot": "content-sha",
        "embeddingProvider": "lexical-hash-256",
        "generationProvider": "extractive-3",
        "gitHead": "abc123",
        "koshaVersion": "0.1.0",
        "sourceSnapshot": "source-sha",
        "updatedAt": "2026-07-07T00:00:00+00:00",
    }


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        "[]",
        '{"updatedAt": 7}',
        json.dumps(
            {
                "updatedAt": "2026-07-07T00:00:00+00:00",
                "command": "sync-docs",
                "gitHead": "abc123",
                "koshaVersion": "0.1.0",
                "contentSnapshot": "content-sha",
                "embeddingProvider": 5,
            }
        ),
    ],
)
def test_sync_state_load_fails_loudly_on_invalid_json(tmp_path: Path, payload: str) -> None:
    path = sync_state_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(payload, encoding="utf-8")

    with pytest.raises(InvalidSyncStateError):
        load_sync_state(path)


def test_content_snapshot_is_stable_and_excludes_sync_metadata(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "z.md").write_text("z\n", encoding="utf-8")
    (tmp_path / "docs" / "a.md").write_text("a\n", encoding="utf-8")
    sync_state_path(tmp_path).parent.mkdir()
    sync_state_path(tmp_path).write_text('{"updatedAt":"old"}\n', encoding="utf-8")

    before = content_snapshot(tmp_path, ["docs", ".kosha/sync-state.json"])
    sync_state_path(tmp_path).write_text('{"updatedAt":"new"}\n', encoding="utf-8")
    after = content_snapshot(tmp_path, [".kosha/sync-state.json", "docs"])

    assert [entry.path for entry in before.entries] == ["docs/a.md", "docs/z.md"]
    assert before == after


def test_content_snapshot_changes_when_meaningful_content_changes(tmp_path: Path) -> None:
    path = tmp_path / "README.md"
    path.write_text("old\n", encoding="utf-8")
    before = content_snapshot(tmp_path, ["README.md"])

    path.write_text("new\n", encoding="utf-8")

    assert content_snapshot(tmp_path, ["README.md"]).sha256 != before.sha256


def test_content_snapshot_fails_loudly_on_missing_explicit_path(tmp_path: Path) -> None:
    with pytest.raises(SnapshotError):
        content_snapshot(tmp_path, ["docs/missing.md"])


def test_decide_sync_skips_clean_unchanged_tree(tmp_path: Path) -> None:
    repo = _seed_sync_repo(tmp_path)
    snapshot = content_snapshot(repo, ["docs/generated.md"])
    recorded_head = current_git_head(repo)

    decision = decide_sync(
        repo,
        recorded_git_head=recorded_head,
        recorded_updated_at="2026-07-07T00:00:00+00:00",
        recorded_content_snapshot=snapshot.sha256,
        current_content_snapshot=snapshot,
        source_paths=["src"],
    )

    assert decision.noop
    assert decision.reason is SyncDecisionReason.NOOP


def test_decide_sync_requires_recheck_for_uncommitted_source_change(tmp_path: Path) -> None:
    repo = _seed_sync_repo(tmp_path)
    snapshot = content_snapshot(repo, ["docs/generated.md"])
    recorded_head = current_git_head(repo)
    (repo / "src" / "app.py").write_text("print('changed')\n", encoding="utf-8")

    decision = decide_sync(
        repo,
        recorded_git_head=recorded_head,
        recorded_updated_at="2026-07-07T00:00:00+00:00",
        recorded_content_snapshot=snapshot.sha256,
        current_content_snapshot=snapshot,
        source_paths=["src"],
    )

    assert not decision.noop
    assert decision.reason is SyncDecisionReason.SOURCE_CHANGED
    assert decision.changed_paths == ("src/app.py",)


def test_decide_sync_accepts_absolute_source_paths(tmp_path: Path) -> None:
    repo = _seed_sync_repo(tmp_path)
    snapshot = content_snapshot(repo, ["docs/generated.md"])
    recorded_head = current_git_head(repo)
    (repo / "src" / "app.py").write_text("print('changed')\n", encoding="utf-8")

    decision = decide_sync(
        repo,
        recorded_git_head=recorded_head,
        recorded_updated_at="2026-07-07T00:00:00+00:00",
        recorded_content_snapshot=snapshot.sha256,
        current_content_snapshot=snapshot,
        source_paths=[repo / "src"],
    )

    assert decision.reason is SyncDecisionReason.SOURCE_CHANGED
    assert decision.changed_paths == ("src/app.py",)


def test_decide_sync_detects_workspace_rename_out_of_source_prefix(tmp_path: Path) -> None:
    repo = _seed_sync_repo(tmp_path)
    snapshot = content_snapshot(repo, ["docs/generated.md"])
    recorded_head = current_git_head(repo)
    (repo / "lib").mkdir()
    _git(repo, "mv", "src/app.py", "lib/app.py")

    decision = decide_sync(
        repo,
        recorded_git_head=recorded_head,
        recorded_updated_at="2026-07-07T00:00:00+00:00",
        recorded_content_snapshot=snapshot.sha256,
        current_content_snapshot=snapshot,
        source_paths=["src"],
    )

    assert decision.reason is SyncDecisionReason.SOURCE_CHANGED
    assert decision.changed_paths == ("src/app.py",)


def test_decide_sync_requires_write_when_generated_content_changes(tmp_path: Path) -> None:
    repo = _seed_sync_repo(tmp_path)
    snapshot = content_snapshot(repo, ["docs/generated.md"])
    recorded_head = current_git_head(repo)
    (repo / "docs" / "generated.md").write_text("changed generated output\n", encoding="utf-8")

    decision = decide_sync(
        repo,
        recorded_git_head=recorded_head,
        recorded_updated_at="2026-07-07T00:00:00+00:00",
        recorded_content_snapshot=snapshot.sha256,
        current_content_snapshot=content_snapshot(repo, ["docs/generated.md"]),
        source_paths=["src"],
    )

    assert not decision.noop
    assert decision.reason is SyncDecisionReason.CONTENT_CHANGED


def test_decide_sync_skips_docs_only_commit_when_generated_content_unchanged(
    tmp_path: Path,
) -> None:
    repo = _seed_sync_repo(tmp_path)
    snapshot = content_snapshot(repo, ["docs/generated.md"])
    recorded_head = current_git_head(repo)
    (repo / "docs" / "notes.md").write_text("hand-authored note\n", encoding="utf-8")
    _commit_all(repo, "docs: add note")

    decision = decide_sync(
        repo,
        recorded_git_head=recorded_head,
        recorded_updated_at="2026-07-07T00:00:00+00:00",
        recorded_content_snapshot=snapshot.sha256,
        current_content_snapshot=content_snapshot(repo, ["docs/generated.md"]),
        source_paths=["src"],
    )

    assert decision.noop
    assert decision.reason is SyncDecisionReason.NOOP


def test_decide_sync_requires_recheck_for_source_commit(tmp_path: Path) -> None:
    repo = _seed_sync_repo(tmp_path)
    snapshot = content_snapshot(repo, ["docs/generated.md"])
    recorded_head = current_git_head(repo)
    (repo / "src" / "app.py").write_text("print('changed')\n", encoding="utf-8")
    _commit_all(repo, "feat: change source")

    decision = decide_sync(
        repo,
        recorded_git_head=recorded_head,
        recorded_updated_at="2026-07-07T00:00:00+00:00",
        recorded_content_snapshot=snapshot.sha256,
        current_content_snapshot=content_snapshot(repo, ["docs/generated.md"]),
        source_paths=["src"],
    )

    assert not decision.noop
    assert decision.reason is SyncDecisionReason.SOURCE_CHANGED
    assert decision.changed_paths == ("src/app.py",)


def test_decide_sync_skips_metadata_only_change(tmp_path: Path) -> None:
    repo = _seed_sync_repo(tmp_path)
    snapshot = content_snapshot(repo, ["docs/generated.md", ".kosha/sync-state.json"])
    recorded_head = current_git_head(repo)
    sync_state_path(repo).write_text('{"updatedAt":"new"}\n', encoding="utf-8")

    decision = decide_sync(
        repo,
        recorded_git_head=recorded_head,
        recorded_updated_at="2026-07-07T00:00:00+00:00",
        recorded_content_snapshot=snapshot.sha256,
        current_content_snapshot=content_snapshot(
            repo,
            ["docs/generated.md", ".kosha/sync-state.json"],
        ),
        source_paths=["src"],
    )

    assert decision.noop
    assert decision.reason is SyncDecisionReason.NOOP


def test_decide_sync_uses_timestamp_fallback_without_recorded_git_head(
    tmp_path: Path,
) -> None:
    repo = _seed_sync_repo(tmp_path)
    snapshot = content_snapshot(repo, ["docs/generated.md"])

    clean = decide_sync(
        repo,
        recorded_git_head=None,
        recorded_updated_at="2999-01-01T00:00:00+00:00",
        recorded_content_snapshot=snapshot.sha256,
        current_content_snapshot=snapshot,
        source_paths=["src"],
    )
    dirty = decide_sync(
        repo,
        recorded_git_head=None,
        recorded_updated_at="2000-01-01T00:00:00+00:00",
        recorded_content_snapshot=snapshot.sha256,
        current_content_snapshot=snapshot,
        source_paths=["src"],
    )

    assert clean.noop
    assert dirty.reason is SyncDecisionReason.SOURCE_CHANGED
    assert dirty.changed_paths == ("src/app.py",)


def test_decide_sync_rejects_naive_timestamp_fallback(tmp_path: Path) -> None:
    repo = _seed_sync_repo(tmp_path)
    snapshot = content_snapshot(repo, ["docs/generated.md"])

    with pytest.raises(SyncDecisionError):
        decide_sync(
            repo,
            recorded_git_head=None,
            recorded_updated_at="2026-07-07T00:00:00",
            recorded_content_snapshot=snapshot.sha256,
            current_content_snapshot=snapshot,
            source_paths=["src"],
        )


def _seed_sync_repo(path: Path) -> Path:
    (path / "src").mkdir()
    (path / "docs").mkdir()
    sync_state_path(path).parent.mkdir()
    (path / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (path / "docs" / "generated.md").write_text("generated\n", encoding="utf-8")
    sync_state_path(path).write_text('{"updatedAt":"old"}\n', encoding="utf-8")
    _git(path, "init")
    _git(path, "config", "user.name", "Kosha Tests")
    _git(path, "config", "user.email", "kosha@example.invalid")
    _commit_all(path, "chore: seed")
    return path


def _commit_all(repo: Path, message: str) -> None:
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", message)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ("git", *args),
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout
