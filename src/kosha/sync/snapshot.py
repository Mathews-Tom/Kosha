"""Deterministic content snapshots for generated sync surfaces."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from kosha.sync.state import SYNC_STATE_RELATIVE_PATH

DEFAULT_SNAPSHOT_EXCLUDES: tuple[Path, ...] = (SYNC_STATE_RELATIVE_PATH, Path(".git"))


class SnapshotError(RuntimeError):
    """A content snapshot could not be computed from a stable file tree."""


@dataclass(frozen=True)
class SnapshotEntry:
    """One meaningful file included in a content snapshot."""

    path: str
    sha256: str


@dataclass(frozen=True)
class ContentSnapshot:
    """A deterministic digest plus the per-file hashes that produced it."""

    sha256: str
    entries: tuple[SnapshotEntry, ...]


def content_snapshot(
    root: Path,
    paths: Iterable[Path | str] | None = None,
    *,
    exclude: Iterable[Path | str] = DEFAULT_SNAPSHOT_EXCLUDES,
) -> ContentSnapshot:
    """Hash meaningful content under ``root`` with stable ordering.

    ``exclude`` is matched against repository-relative POSIX paths. Excluding
    ``.kosha/sync-state.json`` by default keeps metadata-only updates from
    producing a new content digest.
    """

    resolved_root = root.resolve()
    excluded = frozenset(_relative_posix(path) for path in exclude)
    entries = tuple(
        SnapshotEntry(path=relative_path, sha256=_file_sha256(path))
        for relative_path, path in _iter_snapshot_files(resolved_root, paths, excluded)
    )
    digest = hashlib.sha256()
    for entry in entries:
        digest.update(entry.path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(entry.sha256.encode("ascii"))
        digest.update(b"\0")
    return ContentSnapshot(sha256=digest.hexdigest(), entries=entries)


def _iter_snapshot_files(
    root: Path,
    paths: Iterable[Path | str] | None,
    excluded: frozenset[str],
) -> tuple[tuple[str, Path], ...]:
    candidates = tuple(paths) if paths is not None else (Path("."),)
    files: list[tuple[str, Path]] = []
    for candidate in candidates:
        absolute = _absolute_candidate(root, candidate)
        relative = _relative_to_root(root, absolute)
        if _is_excluded(relative, excluded):
            continue
        if not absolute.exists():
            raise SnapshotError(f"snapshot path is missing: {relative}")
        if absolute.is_dir():
            for file_path in absolute.rglob("*"):
                if not file_path.is_file():
                    continue
                child_relative = _relative_to_root(root, file_path)
                if not _is_excluded(child_relative, excluded):
                    files.append((child_relative, file_path))
            continue
        if not absolute.is_file():
            raise SnapshotError(f"snapshot path is not a regular file: {relative}")
        files.append((relative, absolute))
    return tuple(sorted(set(files), key=lambda item: item[0]))


def _absolute_candidate(root: Path, candidate: Path | str) -> Path:
    path = Path(candidate)
    if path.is_absolute():
        return path.resolve()
    return (root / path).resolve()


def _relative_to_root(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError as exc:
        raise SnapshotError(f"snapshot path is outside root: {path}") from exc


def _relative_posix(path: Path | str) -> str:
    return Path(path).as_posix().strip("/")


def _is_excluded(relative: str, excluded: frozenset[str]) -> bool:
    return any(relative == item or relative.startswith(f"{item}/") for item in excluded)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except FileNotFoundError as exc:
        raise SnapshotError(f"snapshot path disappeared while reading: {path}") from exc
    return digest.hexdigest()
