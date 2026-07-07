"""Sync state and no-op foundation tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kosha.sync import (
    InvalidSyncStateError,
    ProviderState,
    SnapshotError,
    SyncState,
    content_snapshot,
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
