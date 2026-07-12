"""One concrete, private, content-addressed filesystem evidence store.

Objects are written before manifests, using same-directory temporary file
plus atomic replace, with POSIX ``0700`` directories and ``0600`` files where
the platform supports them (DEVELOPMENT_PLAN.md M2; enhancement plan §9).

This is the only storage implementation. It intentionally exposes no
protocol, base class, backend registry, or database abstraction -- adding a
second implementation is a precondition for introducing one, not this
milestone's concern.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from contextlib import suppress
from pathlib import Path

import pydantic

from kosha.evidence.model import (
    SourceRun,
    hash_evidence_text,
    source_run_from_json,
    source_run_to_json,
)
from kosha.evidence.paths import manifest_path, object_path, validate_digest

_DIR_MODE = 0o700
_FILE_MODE = 0o600


class EvidenceCorruptionError(RuntimeError):
    """Raised when stored evidence state is missing, malformed, or internally inconsistent."""


class EvidenceConflictError(RuntimeError):
    """Raised when content hashing to an existing digest has different bytes on disk."""


class EvidenceStore:
    """A private, append-only, content-addressed store rooted at one directory.

    ``root`` is caller-supplied and never computed here -- see
    :func:`kosha.evidence.paths.evidence_root` for the default operator-private
    location. Passing an arbitrary ``root`` (e.g. ``tmp_path`` in tests) is the
    injection point; this class performs no environment lookups itself.
    """

    def __init__(self, root: Path) -> None:
        self._root = root

    @property
    def root(self) -> Path:
        """Return this store's root directory."""
        return self._root

    def put_object(self, normalized_text: str) -> str:
        """Idempotently persist ``normalized_text``, returning its SHA-256 digest.

        Writing the same text twice is a no-op past the first call. Content
        that hashes to an existing digest but disagrees with the bytes
        already on disk fails loud rather than silently overwriting.
        """
        payload = normalized_text.encode("utf-8")
        digest = hash_evidence_text(normalized_text)
        path = object_path(self._root, digest)
        if path.exists():
            existing = path.read_bytes()
            if existing != payload:
                raise EvidenceConflictError(
                    f"object at digest {digest} already exists with different content"
                )
            return digest
        _ensure_private_dir(path.parent)
        _atomic_write_bytes(path, payload)
        return digest

    def has_object(self, digest: str) -> bool:
        """Return whether a validated ``digest`` currently has a stored object."""
        return object_path(self._root, validate_digest(digest)).exists()

    def read_object(self, digest: str) -> str:
        """Return the normalized text stored under ``digest``, failing loud on corruption."""
        validated = validate_digest(digest)
        path = object_path(self._root, validated)
        if not path.exists():
            raise EvidenceCorruptionError(f"no evidence object for digest {validated}")
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != validated:
            raise EvidenceCorruptionError(f"stored object at digest {validated} is corrupt")
        return payload.decode("utf-8")

    def write_run(self, run: SourceRun) -> Path:
        """Persist ``run``'s manifest only after every referenced object exists.

        Never leaves a manifest referencing a missing object: the existence
        check runs before any write, and the write itself is atomic.
        """
        for document in run.evidence:
            if not self.has_object(document.sha256):
                raise EvidenceCorruptionError(
                    f"run {run.run_id!r} references missing evidence object {document.sha256}"
                )
        path = manifest_path(self._root, run.run_id)
        _ensure_private_dir(path.parent)
        payload = (
            json.dumps(source_run_to_json(run), sort_keys=True, indent=2).encode("utf-8") + b"\n"
        )
        _atomic_write_bytes(path, payload)
        return path

    def read_run(self, run_id: str) -> SourceRun:
        """Load and validate the manifest for ``run_id``, failing loud on any defect."""
        path = manifest_path(self._root, run_id)
        if not path.exists():
            raise EvidenceCorruptionError(f"no source-run manifest for {run_id!r}")
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise EvidenceCorruptionError(
                f"malformed source-run manifest at {path}: {exc}"
            ) from exc
        try:
            run = source_run_from_json(raw)
        except (TypeError, pydantic.ValidationError) as exc:
            raise EvidenceCorruptionError(f"invalid source-run manifest at {path}: {exc}") from exc
        for document in run.evidence:
            if not self.has_object(document.sha256):
                raise EvidenceCorruptionError(
                    f"source-run {run_id!r} references missing evidence object {document.sha256}"
                )
        return run

    def list_run_ids(self) -> tuple[str, ...]:
        """Return every stored source-run id, sorted, or empty if none exist yet.

        Enumerates the ``runs`` directory's manifest filenames directly rather
        than requiring a caller to already know a run id -- the entry point
        :func:`~kosha.evidence.verify.verify_evidence` uses to discover every
        manifest a vault holds, not just the ones a commit trailer references.
        """
        runs_dir = self._root / "runs"
        if not runs_dir.is_dir():
            return ()
        return tuple(sorted(path.stem for path in runs_dir.glob("*.json")))


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
