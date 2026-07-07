"""Internal sync-state foundation for low-churn generated surfaces."""

from __future__ import annotations

from kosha.sync.snapshot import ContentSnapshot, SnapshotEntry, SnapshotError, content_snapshot
from kosha.sync.state import (
    InvalidSyncStateError,
    ProviderState,
    SyncState,
    load_sync_state,
    save_sync_state,
    sync_state_path,
)

__all__ = [
    "ContentSnapshot",
    "InvalidSyncStateError",
    "ProviderState",
    "SnapshotEntry",
    "SnapshotError",
    "SyncState",
    "content_snapshot",
    "load_sync_state",
    "save_sync_state",
    "sync_state_path",
]
