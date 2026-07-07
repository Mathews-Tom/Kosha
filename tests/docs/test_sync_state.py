"""Sync state and no-op foundation tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kosha.sync import (
    InvalidSyncStateError,
    ProviderState,
    SyncState,
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
