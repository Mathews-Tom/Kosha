"""Repository-scoped sync metadata for generated Kosha surfaces."""

from __future__ import annotations

import json
from dataclasses import dataclass
from json import JSONDecodeError
from pathlib import Path

SYNC_STATE_RELATIVE_PATH = Path(".kosha/sync-state.json")


class InvalidSyncStateError(ValueError):
    """The persisted sync-state JSON is missing required structure or fields."""


@dataclass(frozen=True)
class ProviderState:
    """Provider identities recorded when generated status depends on model outputs."""

    embedding: str | None = None
    generation: str | None = None


@dataclass(frozen=True)
class SyncState:
    """One successful sync's repository metadata and meaningful-content hashes."""

    updated_at: str
    command: str
    git_head: str | None
    kosha_version: str
    content_snapshot: str
    source_snapshot: str | None = None
    providers: ProviderState = ProviderState()


def sync_state_path(repo_root: Path) -> Path:
    """Return the repository-scoped sync-state path under ``repo_root``."""

    return repo_root / SYNC_STATE_RELATIVE_PATH


def load_sync_state(path: Path) -> SyncState:
    """Load and validate a sync-state JSON document.

    A missing file is a caller decision, not a corrupt state, so it naturally
    raises :class:`FileNotFoundError`. Malformed JSON and schema mismatches are
    wrapped in :class:`InvalidSyncStateError` with the state path attached.
    """

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except JSONDecodeError as exc:
        raise InvalidSyncStateError(f"invalid sync state JSON at {path}: {exc.msg}") from exc
    try:
        return sync_state_from_json(raw)
    except (TypeError, ValueError) as exc:
        raise InvalidSyncStateError(f"invalid sync state at {path}: {exc}") from exc


def save_sync_state(path: Path, state: SyncState) -> None:
    """Persist ``state`` as stable, reviewable JSON."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(sync_state_to_json(state), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def sync_state_from_json(raw: object) -> SyncState:
    """Build a :class:`SyncState` from decoded JSON with fail-loud validation."""

    data = _expect_object(raw, "sync state")
    return SyncState(
        updated_at=_expect_str(data, "updatedAt"),
        command=_expect_str(data, "command"),
        git_head=_expect_optional_str(data, "gitHead"),
        kosha_version=_expect_str(data, "koshaVersion"),
        content_snapshot=_expect_str(data, "contentSnapshot"),
        source_snapshot=_expect_optional_str(data, "sourceSnapshot"),
        providers=ProviderState(
            embedding=_expect_optional_str(data, "embeddingProvider"),
            generation=_expect_optional_str(data, "generationProvider"),
        ),
    )


def sync_state_to_json(state: SyncState) -> dict[str, object]:
    """Return the stable JSON object written for ``state``."""

    return {
        "command": state.command,
        "contentSnapshot": state.content_snapshot,
        "embeddingProvider": state.providers.embedding,
        "generationProvider": state.providers.generation,
        "gitHead": state.git_head,
        "koshaVersion": state.kosha_version,
        "sourceSnapshot": state.source_snapshot,
        "updatedAt": state.updated_at,
    }


def _expect_object(raw: object, name: str) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise TypeError(f"{name} must be a JSON object")
    return {str(key): value for key, value in raw.items()}


def _expect_str(data: dict[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or value == "":
        raise ValueError(f"sync state field {key!r} must be a non-empty string")
    return value


def _expect_optional_str(data: dict[str, object], key: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or value == "":
        raise ValueError(f"sync state field {key!r} must be a non-empty string or null")
    return value
