"""Durable, mutable knowledge-gap ledger store (DEVELOPMENT_PLAN.md M10).

One JSON array per bundle at ``~/.kosha/gaps/<bundle-identity>/gaps.json`` by
default, written with the same same-directory-temp-file-plus-atomic-replace
discipline :mod:`kosha.evidence.store` / :mod:`kosha.connectors.state` use,
and the same ``0700``/``0600`` private permissions. A gap record is never
deleted here: :meth:`GapLedgerStore.answer`, :meth:`~GapLedgerStore.invalidate`,
and :meth:`~GapLedgerStore.mark_stale` replace a gap's stored record in
place, but every gap this bundle has ever accumulated -- including terminal
ones -- is always returned by :meth:`~GapLedgerStore.load` (enhancement plan
§17: "Stale and invalidated gaps remain auditable").

This is a separate surface from the BLOCK-lane review queue
(:mod:`kosha.approve.queue`) by design: that queue represents proposed
*plan changes* awaiting a yes/no decision, and a knowledge gap is not a
proposed edit -- forcing it through ``ReviewQueueItem`` would require
inventing a fake `ChangePlan` for something that never mutates the bundle.
The gap lifecycle instead reuses the review/audit *data*: every gap traces
back to :class:`kosha.audit.export.ComplianceReport`, the same deterministic
evidence ``kosha audit export`` already reports (see
:mod:`kosha.gaps.produce`), and resolution always cites the review queue's or
audit trail's own artifacts (a commit SHA, an evidence digest) rather than
duplicating them.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable, Sequence
from contextlib import suppress
from datetime import datetime
from pathlib import Path

import pydantic

from kosha.gaps.model import GapStatus, KnowledgeGap
from kosha.gaps.paths import ledger_path

_DIR_MODE = 0o700
_FILE_MODE = 0o600


class GapLedgerCorruptionError(RuntimeError):
    """Raised when the stored gap ledger is missing, malformed, or internally inconsistent."""


class UnknownGapError(KeyError):
    """Raised when a lifecycle action targets a ``gap_id`` the ledger has never recorded."""


class GapLedgerStore:
    """One private, atomic, per-bundle JSON knowledge-gap ledger.

    ``root`` is caller-supplied and never computed here -- see
    :func:`kosha.gaps.paths.gaps_root` for the default operator-private
    location. Passing an arbitrary ``root`` (e.g. ``tmp_path`` in tests) is
    the injection point; this class performs no environment lookups itself.
    """

    def __init__(self, root: Path) -> None:
        self._root = root

    @property
    def root(self) -> Path:
        """Return this store's root directory."""
        return self._root

    def load(self) -> tuple[KnowledgeGap, ...]:
        """Return every gap this bundle has ever recorded, sorted by ``gap_id``.

        Fails loud on a present-but-malformed ledger file: never falls back
        to an empty ledger for a corrupt one.
        """
        path = ledger_path(self._root)
        if not path.exists():
            return ()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GapLedgerCorruptionError(f"malformed gap ledger at {path}: {exc}") from exc
        if not isinstance(raw, list):
            raise GapLedgerCorruptionError(f"gap ledger at {path} is not a JSON array")
        try:
            gaps = tuple(KnowledgeGap.model_validate(item) for item in raw)
        except (TypeError, pydantic.ValidationError) as exc:
            raise GapLedgerCorruptionError(
                f"invalid gap record in ledger at {path}: {exc}"
            ) from exc
        return _sorted(gaps)

    def save(self, gaps: Sequence[KnowledgeGap]) -> Path:
        """Atomically persist the full ``gaps`` set, replacing any prior ledger."""
        path = ledger_path(self._root)
        _ensure_private_dir(path.parent)
        payload = (
            json.dumps(
                [gap.model_dump(mode="json") for gap in _sorted(gaps)],
                sort_keys=True,
                indent=2,
            ).encode("utf-8")
            + b"\n"
        )
        _atomic_write_bytes(path, payload)
        return path

    def merge_events(self, events: Sequence[KnowledgeGap]) -> tuple[KnowledgeGap, ...]:
        """Merge fresh producer ``events`` into the stored ledger and persist it.

        A repeated event (same ``gap_id``) updates its existing gap's
        ``last_seen_at``/``seen_count``/accumulated links via
        :meth:`~kosha.gaps.model.KnowledgeGap.observe` instead of creating a
        duplicate record. A never-seen ``gap_id`` is inserted as a new OPEN
        gap. Returns the full merged ledger.
        """
        existing = {gap.gap_id: gap for gap in self.load()}
        for event in events:
            if event.status is not GapStatus.OPEN:
                raise ValueError(
                    "a producer event must be OPEN; lifecycle transitions go through "
                    "answer()/invalidate()/mark_stale(), never merge_events()"
                )
            prior = existing.get(event.gap_id)
            existing[event.gap_id] = (
                event
                if prior is None
                else prior.observe(
                    at=event.last_seen_at,
                    source_run_ids=event.source_run_ids,
                    evidence_sha256=event.evidence_sha256,
                    affected_concept_ids=event.affected_concept_ids,
                )
            )
        merged = _sorted(list(existing.values()))
        self.save(merged)
        return merged

    def answer(self, gap_id: str, *, resolution_reference: str, at: datetime) -> KnowledgeGap:
        """Transition ``gap_id`` to ``answered``, linking evidence or a reviewed change."""
        return self._transition(
            gap_id, lambda gap: gap.answer(resolution_reference=resolution_reference, at=at)
        )

    def invalidate(self, gap_id: str, *, resolution_reference: str, at: datetime) -> KnowledgeGap:
        """Transition ``gap_id`` to ``invalidated`` (reviewed as not a real gap)."""
        return self._transition(
            gap_id, lambda gap: gap.invalidate(resolution_reference=resolution_reference, at=at)
        )

    def mark_stale(self, gap_id: str, *, at: datetime) -> KnowledgeGap:
        """Transition ``gap_id`` to ``stale`` (aged out without resolution)."""
        return self._transition(gap_id, lambda gap: gap.mark_stale(at=at))

    def _transition(
        self, gap_id: str, apply: Callable[[KnowledgeGap], KnowledgeGap]
    ) -> KnowledgeGap:
        gaps = {gap.gap_id: gap for gap in self.load()}
        prior = gaps.get(gap_id)
        if prior is None:
            raise UnknownGapError(gap_id)
        updated = apply(prior)
        gaps[gap_id] = updated
        self.save(tuple(gaps.values()))
        return updated


def _sorted(gaps: Sequence[KnowledgeGap]) -> tuple[KnowledgeGap, ...]:
    return tuple(sorted(gaps, key=lambda gap: gap.gap_id))


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
