"""Internal sync-state foundation for low-churn generated surfaces."""

from __future__ import annotations

from kosha.sync.check import (
    SyncChecker,
    SyncCheckReport,
    SyncMismatch,
    default_sync_checkers,
    render_sync_check_text,
    run_sync_check,
    sync_check_json,
)
from kosha.sync.decision import (
    SyncDecision,
    SyncDecisionError,
    SyncDecisionReason,
    current_git_head,
    decide_sync,
    source_changes_after_timestamp,
    source_changes_since,
)
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
    "SyncCheckReport",
    "SyncChecker",
    "SyncDecision",
    "SyncDecisionError",
    "SyncDecisionReason",
    "SyncMismatch",
    "SyncState",
    "content_snapshot",
    "current_git_head",
    "decide_sync",
    "default_sync_checkers",
    "load_sync_state",
    "render_sync_check_text",
    "run_sync_check",
    "save_sync_state",
    "source_changes_after_timestamp",
    "source_changes_since",
    "sync_check_json",
    "sync_state_path",
]
