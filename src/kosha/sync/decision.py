"""No-op decisions for low-churn sync runs."""

from __future__ import annotations

import subprocess
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from kosha.sync.snapshot import ContentSnapshot


class SyncDecisionReason(StrEnum):
    """Why a sync run should write, re-check, or skip."""

    NOOP = "noop"
    CONTENT_CHANGED = "content_changed"
    SOURCE_CHANGED = "source_changed"


class SyncDecisionError(RuntimeError):
    """The repository state needed for a sync decision could not be read."""


@dataclass(frozen=True)
class SyncDecision:
    """The no-op decision for one sync surface set."""

    noop: bool
    reason: SyncDecisionReason
    changed_paths: tuple[str, ...] = field(default_factory=tuple)


def current_git_head(repo_root: Path) -> str:
    """Return ``HEAD`` for ``repo_root`` or fail loudly outside a valid git repo."""

    return _git(repo_root, "rev-parse", "HEAD").strip()


def source_changes_since(
    repo_root: Path,
    git_head: str,
    source_paths: Iterable[Path | str],
) -> tuple[str, ...]:
    """Return tracked, staged, unstaged, and untracked source paths changed since ``git_head``."""

    prefixes = _prefixes(repo_root, source_paths)
    changed = set(_committed_paths_since(repo_root, git_head))
    changed.update(_workspace_paths(repo_root))
    return tuple(path for path in sorted(changed) if _matches_prefix(path, prefixes))


def source_changes_after_timestamp(
    repo_root: Path,
    updated_at: str,
    source_paths: Iterable[Path | str],
) -> tuple[str, ...]:
    """Timestamp fallback for state written before a precise ``gitHead`` existed."""

    cutoff = _parse_timestamp(updated_at)
    changed: list[str] = []
    for relative, absolute in _iter_source_files(repo_root, source_paths):
        modified_at = datetime.fromtimestamp(absolute.stat().st_mtime, tz=cutoff.tzinfo)
        if modified_at > cutoff:
            changed.append(relative)
    return tuple(sorted(changed))


def decide_sync(
    repo_root: Path,
    *,
    recorded_git_head: str | None,
    recorded_updated_at: str,
    recorded_content_snapshot: str,
    current_content_snapshot: ContentSnapshot,
    source_paths: Iterable[Path | str],
    current_head: str | None = None,
) -> SyncDecision:
    """Decide whether a sync run can skip all writes and checks.

    Content drift wins first because generated output changed. Source drift wins
    next because a checker/writer must re-render from source-of-truth inputs even
    if generated files happen to be unchanged before rendering.
    """

    if current_content_snapshot.sha256 != recorded_content_snapshot:
        return SyncDecision(noop=False, reason=SyncDecisionReason.CONTENT_CHANGED)

    if recorded_git_head is None:
        changed_paths = source_changes_after_timestamp(repo_root, recorded_updated_at, source_paths)
    else:
        resolved_head = current_head or current_git_head(repo_root)
        if resolved_head == recorded_git_head:
            changed_paths = _filtered_workspace_paths(repo_root, source_paths)
        else:
            changed_paths = source_changes_since(repo_root, recorded_git_head, source_paths)
    if changed_paths:
        return SyncDecision(
            noop=False,
            reason=SyncDecisionReason.SOURCE_CHANGED,
            changed_paths=changed_paths,
        )
    return SyncDecision(noop=True, reason=SyncDecisionReason.NOOP)


def _committed_paths_since(repo_root: Path, git_head: str) -> tuple[str, ...]:
    return _lines(_git(repo_root, "diff", "--name-only", f"{git_head}..HEAD"))


def _filtered_workspace_paths(
    repo_root: Path,
    source_paths: Iterable[Path | str],
) -> tuple[str, ...]:
    prefixes = _prefixes(repo_root, source_paths)
    return tuple(path for path in _workspace_paths(repo_root) if _matches_prefix(path, prefixes))


def _workspace_paths(repo_root: Path) -> tuple[str, ...]:
    porcelain = _git(repo_root, "status", "--porcelain", "--untracked-files=all")
    paths: list[str] = []
    for line in porcelain.splitlines():
        if not line:
            continue
        raw_path = line[3:]
        if " -> " in raw_path:
            old_path, new_path = raw_path.rsplit(" -> ", maxsplit=1)
            paths.extend((old_path.strip('"'), new_path.strip('"')))
            continue
        paths.append(raw_path.strip('"'))
    return tuple(sorted(paths))


def _iter_source_files(
    repo_root: Path,
    source_paths: Iterable[Path | str],
) -> tuple[tuple[str, Path], ...]:
    root = repo_root.resolve()
    files: list[tuple[str, Path]] = []
    for source_path in source_paths:
        absolute = _absolute_candidate(root, source_path)
        if not absolute.exists():
            raise SyncDecisionError(f"source path is missing: {_relative_to_root(root, absolute)}")
        if absolute.is_dir():
            for child in absolute.rglob("*"):
                if child.is_file():
                    files.append((_relative_to_root(root, child), child))
            continue
        if not absolute.is_file():
            raise SyncDecisionError(f"source path is not a regular file: {absolute}")
        files.append((_relative_to_root(root, absolute), absolute))
    return tuple(sorted(set(files), key=lambda item: item[0]))


def _prefixes(repo_root: Path, paths: Iterable[Path | str]) -> tuple[str, ...]:
    root = repo_root.resolve()
    return tuple(sorted(_relative_to_root(root, _absolute_candidate(root, path)) for path in paths))


def _matches_prefix(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in prefixes)


def _relative_posix(path: Path | str) -> str:
    return Path(path).as_posix().strip("/")


def _absolute_candidate(root: Path, candidate: Path | str) -> Path:
    path = Path(candidate)
    if path.is_absolute():
        return path.resolve()
    return (root / path).resolve()


def _relative_to_root(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError as exc:
        raise SyncDecisionError(f"source path is outside root: {path}") from exc


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SyncDecisionError(f"invalid sync updatedAt timestamp: {value}") from exc
    if parsed.tzinfo is None:
        raise SyncDecisionError(f"sync updatedAt timestamp must include a timezone: {value}")
    return parsed


def _git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ("git", *args),
        cwd=repo_root,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise SyncDecisionError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def _lines(value: str) -> tuple[str, ...]:
    return tuple(line for line in value.splitlines() if line)
