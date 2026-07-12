"""Durable, mutable connector cursor-state store (DEVELOPMENT_PLAN.md M6).

Rooted at ``~/.kosha/connectors/<instance-id>/`` by default, honoring
``KOSHA_HOME`` exactly like the evidence vault
(:func:`kosha.evidence.paths.kosha_home`). Wholly separate storage from the
immutable evidence vault: this store never holds source body text, is not
content-addressed, and uses the same same-directory-temp-file-plus-atomic-
replace write discipline as :mod:`kosha.evidence.store` for the same reason
-- a torn write must never leave a state file half-written -- without
sharing an abstraction with it (each store owns its own concrete file I/O;
see ``kosha.evidence.store``'s module docstring).
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from contextlib import suppress
from pathlib import Path

import pydantic

from kosha.connectors.model import ConnectorState
from kosha.evidence.paths import kosha_home, validate_run_id

_DIR_MODE = 0o700
_FILE_MODE = 0o600
_STATE_FILENAME = "state.json"


class ConnectorStateCorruptionError(RuntimeError):
    """Raised when stored connector state is missing, malformed, or internally inconsistent."""


def connectors_root(*, env: Mapping[str, str] | None = None, home: Path | None = None) -> Path:
    """Return the operator-private root every connector instance's state lives under.

    ``home`` overrides the resolved Kosha data root directly (for tests);
    ``env`` is only consulted when ``home`` is omitted.
    """
    base = home if home is not None else kosha_home(env)
    return base / "connectors"


def instance_state_path(root: Path, instance_id: str) -> Path:
    """Return the state file path for a validated ``instance_id`` under a connectors ``root``."""
    return root / validate_run_id(instance_id) / _STATE_FILENAME


class ConnectorStateStore:
    """One private, atomic, per-instance JSON cursor-state store.

    ``root`` is caller-supplied and never computed here -- see
    :func:`connectors_root` for the default operator-private location.
    Passing an arbitrary ``root`` (e.g. ``tmp_path`` in tests) is the
    injection point; this class performs no environment lookups itself.
    """

    def __init__(self, root: Path) -> None:
        self._root = root

    @property
    def root(self) -> Path:
        """Return this store's root directory."""
        return self._root

    def load(self, instance_id: str) -> ConnectorState | None:
        """Return ``instance_id``'s stored state, or ``None`` if it has never run.

        Fails loud on a present-but-malformed state file: never falls back
        to a fresh empty state for a corrupt one.
        """
        path = instance_state_path(self._root, instance_id)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ConnectorStateCorruptionError(
                f"malformed connector state at {path}: {exc}"
            ) from exc
        try:
            return ConnectorState.model_validate(raw)
        except (TypeError, pydantic.ValidationError) as exc:
            raise ConnectorStateCorruptionError(
                f"invalid connector state at {path}: {exc}"
            ) from exc

    def save(self, state: ConnectorState) -> Path:
        """Atomically persist ``state``, replacing any prior state for its instance."""
        path = instance_state_path(self._root, state.instance_id)
        _ensure_private_dir(path.parent)
        payload = (
            json.dumps(state.model_dump(mode="json"), sort_keys=True, indent=2).encode("utf-8")
            + b"\n"
        )
        _atomic_write_bytes(path, payload)
        return path


def _ensure_private_dir(path: Path) -> None:
    """Create ``path`` and any missing parents, enforcing ``0700`` despite umask."""
    missing: list[Path] = []
    cursor = path
    while not cursor.exists():
        missing.append(cursor)
        cursor = cursor.parent
    for directory in reversed(missing):
        directory.mkdir(mode=_DIR_MODE, exist_ok=True)
        _chmod_if_posix(directory, _DIR_MODE)


def _chmod_if_posix(path: Path, mode: int) -> None:
    if os.name == "posix":
        os.chmod(path, mode)


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    """Write ``payload`` to ``path`` via same-directory temp file plus atomic replace."""
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        _chmod_if_posix(Path(tmp_name), _FILE_MODE)
        os.replace(tmp_name, path)
    except BaseException:
        with suppress(OSError):
            os.remove(tmp_name)
        raise
