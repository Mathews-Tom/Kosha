"""Operator recovery: backup-tag restore and index reindex (M8 PR-4).

Two recovery primitives over the existing safety substrates:

* **restore** — bring a bundle back to the state a daily ``backup/<date>`` tag
  (:meth:`~kosha.git_store.GitStore.tag_daily_backup`) recorded.
* **reindex** — regenerate any ``index.md`` files that drifted from the
  bundle's actual concepts (:mod:`kosha.indexlog.index`).

Both share the same operator-safety contract: a ``describe_*`` function shows
the exact refs/files an action would touch without writing anything, and the
matching ``apply_*`` function is the only thing that mutates — always on its
own branch (never `main` directly, matching the ingest governance invariant),
always behind the same :class:`~kosha.git_store.IngestLock` `ingest()` uses
(recovery mutates the same shared working tree), and only after a fresh,
uniquely-timestamped ``recovery-safety/<timestamp>`` tag is created so the
pre-recovery state is itself always one tag away, never silently lost. This is
a distinct namespace from the ingest pipeline's daily ``backup/<date>`` tag —
reusing that one would force-move (and so silently destroy) the very backup
tag a same-day restore is reading from. Every apply returns a
:class:`RecoveryRecord` — the durable audit trail a non-Git-expert operator
can inspect or archive.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kosha.git_store import GitStore, IngestLock
from kosha.indexlog.index import regenerate_indexes
from kosha.okf import load_bundle

_SAFETY_PREFIX = "recovery-safety"


class RecoveryError(RuntimeError):
    """A recovery precondition failed (e.g. an unknown backup tag)."""


@dataclass(frozen=True)
class BackupTag:
    """One ``backup/<date>`` tag: its name, target commit, and date."""

    name: str
    sha: str
    date: str


@dataclass(frozen=True)
class RestoreChange:
    """One path's git-diff status between the current state and a backup tag."""

    status: str
    path: str


@dataclass(frozen=True)
class RestorePlan:
    """The exact changes restoring to ``tag`` would make; nothing has been written."""

    tag: str
    ref: str
    changes: tuple[RestoreChange, ...] = field(default_factory=tuple)

    @property
    def is_empty(self) -> bool:
        return not self.changes


@dataclass(frozen=True)
class ReindexChange:
    """One ``index.md`` path that drifted from the bundle's current concepts."""

    path: str
    action: str


@dataclass(frozen=True)
class ReindexPlan:
    """The exact ``index.md`` files reindexing would create or update."""

    changes: tuple[ReindexChange, ...] = field(default_factory=tuple)

    @property
    def is_empty(self) -> bool:
        return not self.changes


@dataclass(frozen=True)
class RecoveryRecord:
    """The audit trail for one applied recovery action."""

    action: str
    applied: bool
    timestamp: str
    backup_tag: str | None = None
    branch: str | None = None
    commit_sha: str | None = None
    paths: tuple[str, ...] = field(default_factory=tuple)
    source_ref: str | None = None


def list_backups(store: GitStore) -> list[BackupTag]:
    """List every ``backup/<date>`` tag, oldest first."""
    names = store.tags_matching("backup/")
    return [
        BackupTag(name=name, sha=store.current_sha(name), date=name.removeprefix("backup/"))
        for name in names
    ]


def describe_restore(store: GitStore, tag: str) -> RestorePlan:
    """Show exactly what restoring to ``tag`` would change, without writing anything."""
    if not store.tag_exists(tag):
        raise RecoveryError(f"backup tag not found: {tag}")
    pairs = store.diff_name_status("HEAD", tag)
    changes = tuple(RestoreChange(status=status, path=path) for status, path in pairs)
    return RestorePlan(tag=tag, ref=store.current_sha(tag), changes=changes)


def apply_restore(
    store: GitStore,
    plan: RestorePlan,
    *,
    asof: datetime | None = None,
    branch: str | None = None,
) -> RecoveryRecord:
    """Restore to ``plan.tag``, verifying it still exists immediately before mutating.

    A fresh ``recovery-safety/<timestamp>`` tag is created first — the
    pre-restore state is never lost, even if the restore itself needs undoing.
    """
    asof = asof or datetime.now(UTC)
    if plan.is_empty:
        return RecoveryRecord(action="restore", applied=False, timestamp=asof.isoformat())
    if not store.tag_exists(plan.tag):
        raise RecoveryError(f"backup tag not found: {plan.tag}")
    with IngestLock(store.repo):
        safety_tag = store.create_tag(f"{_SAFETY_PREFIX}/{asof:%Y%m%d%H%M%S}")
        branch_name = branch or f"recovery/restore-{plan.tag.replace('/', '-')}-{asof:%Y%m%d%H%M%S}"
        store.create_branch(branch_name)
        store.restore_tree(plan.tag)
        body = "\n".join(f"- {change.status} {change.path}" for change in plan.changes)
        message = (
            f"chore(recovery): restore from {plan.tag}\n\n{body}\n\n"
            f"Recovery-of: {plan.tag}\nRecovery-ref: {plan.ref}"
        )
        commit_sha = store.commit_staged(message)
    return RecoveryRecord(
        action="restore",
        applied=True,
        timestamp=asof.isoformat(),
        backup_tag=safety_tag,
        branch=branch_name,
        commit_sha=commit_sha,
        paths=tuple(change.path for change in plan.changes),
        source_ref=plan.tag,
    )


def describe_reindex(bundle_root: Path) -> ReindexPlan:
    """Show exactly which ``index.md`` files reindexing would create or update."""
    bundle = load_bundle(bundle_root)
    desired = regenerate_indexes(bundle)
    changes: list[ReindexChange] = []
    for rel_path in sorted(desired):
        content = desired[rel_path]
        full = bundle_root / rel_path
        if not full.is_file():
            changes.append(ReindexChange(path=rel_path, action="create"))
        elif full.read_text(encoding="utf-8") != content:
            changes.append(ReindexChange(path=rel_path, action="update"))
    return ReindexPlan(changes=tuple(changes))


def apply_reindex(
    store: GitStore,
    bundle_root: Path,
    plan: ReindexPlan,
    *,
    asof: datetime | None = None,
    branch: str | None = None,
) -> RecoveryRecord:
    """Write and commit exactly the ``index.md`` files ``plan`` names.

    A fresh ``recovery-safety/<timestamp>`` tag is created first, matching
    :func:`apply_restore`.
    """
    asof = asof or datetime.now(UTC)
    if plan.is_empty:
        return RecoveryRecord(action="reindex", applied=False, timestamp=asof.isoformat())
    with IngestLock(store.repo):
        safety_tag = store.create_tag(f"{_SAFETY_PREFIX}/{asof:%Y%m%d%H%M%S}")
        branch_name = branch or f"recovery/reindex-{asof:%Y%m%d%H%M%S}"
        store.create_branch(branch_name)
        bundle = load_bundle(bundle_root)
        desired = regenerate_indexes(bundle)
        written: list[Path] = []
        for change in plan.changes:
            full = bundle_root / change.path
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(desired[change.path], encoding="utf-8")
            written.append(full)
        body = "\n".join(f"- {change.action} {change.path}" for change in plan.changes)
        message = f"chore(recovery): reindex bundle\n\n{body}"
        commit_sha = store.commit(written, message)
    return RecoveryRecord(
        action="reindex",
        applied=True,
        timestamp=asof.isoformat(),
        backup_tag=safety_tag,
        branch=branch_name,
        commit_sha=commit_sha,
        paths=tuple(change.path for change in plan.changes),
    )


def to_json(record: RecoveryRecord) -> dict[str, Any]:
    """Render ``record`` as a JSON-serializable mapping (tuple fields as lists)."""
    payload = asdict(record)
    payload["paths"] = list(payload["paths"])
    return payload


def append_audit_log(path: Path, record: RecoveryRecord) -> None:
    """Append ``record`` as one JSON line to the audit log at ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(to_json(record)) + "\n")
