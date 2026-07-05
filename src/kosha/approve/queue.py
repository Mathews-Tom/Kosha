"""Shared BLOCK-lane review queue with append-only decision history."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO, cast
from uuid import uuid4

from kosha.approve.autonomy import PlanRouting
from kosha.approve.decision import Decision, normalize_reviewer
from kosha.plan import ChangePlan


@dataclass(frozen=True)
class DecisionRecord:
    """One reviewer action recorded against a queue item."""

    reviewer: str
    decision: Decision
    decided_at: str


@dataclass(frozen=True)
class ReviewQueueItem:
    """One BLOCK-lane change waiting for shared human review."""

    item_id: str
    path: str
    source: str
    created_by: str | None
    created_at: str
    status: str = "pending"
    decisions: tuple[DecisionRecord, ...] = field(default_factory=tuple)


class ReviewQueue:
    """Concurrency-safe JSON queue for BLOCK-lane review items."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock_path = path.with_suffix(path.suffix + ".lock")

    def enqueue(
        self,
        plan: ChangePlan,
        routing: PlanRouting,
        source: str,
        created_by: str | None = None,
    ) -> list[ReviewQueueItem]:
        """Append new BLOCK-lane routes, skipping already-pending duplicates."""

        del plan
        creator = normalize_reviewer(created_by)
        now = _now_iso()
        with self._locked_state() as state:
            pending = {
                (item.source, item.path) for item in state if item.status == "pending"
            }
            items = [
                ReviewQueueItem(
                    item_id=uuid4().hex,
                    path=route.change.path,
                    source=source,
                    created_by=creator,
                    created_at=now,
                )
                for route in routing.blocked()
                if (source, route.change.path) not in pending
            ]
            state.extend(items)
        return items

    def items(self) -> list[ReviewQueueItem]:
        """Return every queue item, preserving persisted order."""

        with self._locked_read_state() as state:
            return list(state)

    def history(self, item_id: str) -> list[DecisionRecord]:
        """Return the append-only decision history for one item."""

        item = self._require_item(item_id)
        return list(item.decisions)

    def record_decision(
        self, item_id: str, reviewer: str, decision: Decision | str
    ) -> ReviewQueueItem:
        """Append a reviewer decision without erasing prior reviewer history."""

        normalized_reviewer = normalize_reviewer(reviewer)
        if normalized_reviewer is None:
            raise ValueError("reviewer identity is required")
        parsed_decision = decision if isinstance(decision, Decision) else Decision(decision)
        record = DecisionRecord(
            reviewer=normalized_reviewer,
            decision=parsed_decision,
            decided_at=_now_iso(),
        )
        with self._locked_state() as state:
            for index, item in enumerate(state):
                if item.item_id == item_id:
                    updated = ReviewQueueItem(
                        item_id=item.item_id,
                        path=item.path,
                        source=item.source,
                        created_by=item.created_by,
                        created_at=item.created_at,
                        status=parsed_decision.value,
                        decisions=(*item.decisions, record),
                    )
                    state[index] = updated
                    return updated
        raise KeyError(item_id)

    def _require_item(self, item_id: str) -> ReviewQueueItem:
        for item in self.items():
            if item.item_id == item_id:
                return item
        raise KeyError(item_id)

    @contextmanager
    def _locked_read_state(self) -> Iterator[list[ReviewQueueItem]]:
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock_path.open("a+", encoding="utf-8") as lock_file:
            _lock(lock_file)
            try:
                yield _read_state(self._path)
            finally:
                _unlock(lock_file)

    @contextmanager
    def _locked_state(self) -> Iterator[list[ReviewQueueItem]]:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock_path.open("a+", encoding="utf-8") as lock_file:
            _lock(lock_file)
            try:
                state = _read_state(self._path)
                yield state
                _write_state(self._path, state)
            finally:
                _unlock(lock_file)


def _read_state(path: Path) -> list[ReviewQueueItem]:
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("review queue file must contain a JSON list")
    return [_item_from_json(item) for item in raw]


def _write_state(path: Path, items: list[ReviewQueueItem]) -> None:
    payload = [_item_to_json(item) for item in items]
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _item_from_json(raw: object) -> ReviewQueueItem:
    data = cast(dict[str, object], raw)
    decisions_raw = data.get("decisions", [])
    if not isinstance(decisions_raw, list):
        raise ValueError("review queue decisions must be a list")
    return ReviewQueueItem(
        item_id=_expect_str(data, "item_id"),
        path=_expect_str(data, "path"),
        source=_expect_str(data, "source"),
        created_by=_expect_optional_str(data, "created_by"),
        created_at=_expect_str(data, "created_at"),
        status=_expect_str(data, "status"),
        decisions=tuple(_decision_from_json(decision) for decision in decisions_raw),
    )


def _item_to_json(item: ReviewQueueItem) -> dict[str, object]:
    return {
        "created_at": item.created_at,
        "created_by": item.created_by,
        "decisions": [_decision_to_json(decision) for decision in item.decisions],
        "item_id": item.item_id,
        "path": item.path,
        "source": item.source,
        "status": item.status,
    }


def _decision_from_json(raw: object) -> DecisionRecord:
    data = cast(dict[str, object], raw)
    return DecisionRecord(
        reviewer=_expect_str(data, "reviewer"),
        decision=Decision(_expect_str(data, "decision")),
        decided_at=_expect_str(data, "decided_at"),
    )


def _decision_to_json(record: DecisionRecord) -> dict[str, str]:
    return {
        "decided_at": record.decided_at,
        "decision": record.decision.value,
        "reviewer": record.reviewer,
    }


def _expect_str(data: dict[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise ValueError(f"review queue field {key!r} must be a string")
    return value


def _expect_optional_str(data: dict[str, object], key: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"review queue field {key!r} must be a string or null")
    return value


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _lock(lock_file: TextIO) -> None:
    import fcntl

    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)


def _unlock(lock_file: TextIO) -> None:
    import fcntl

    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
