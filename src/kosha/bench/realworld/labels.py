"""Held-out label sets for the real-model benchmark (M13).

Two JSONL files under ``evals/realworld/`` carry the ground truth:

* ``queries.jsonl`` — a held-out question set over the external corpus, reusing
  :class:`~kosha.bench.queries.BenchQuery`. Each query names the concept ids a
  correct answer must surface and keywords a correct answer should mention.
* ``maintenance.jsonl`` — labeled maintenance cases. Each new source doc is
  labeled with the routing the loop *should* produce: a ``duplicate`` or
  ``contradiction`` must attach to an existing ``target`` concept (UPDATE), a
  ``novel`` doc must spawn a new concept (CREATE). ``kind`` is retained so the
  report can break quality down by dedup / contradiction.

The sets are *held out*: they are authored against the corpus but never used to
calibrate any strategy's parameters.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from kosha.bench.queries import BenchQuery

# A maintenance case's expected routing outcome and its category.
MAINTENANCE_ACTIONS = frozenset({"UPDATE", "CREATE"})
MAINTENANCE_KINDS = frozenset({"duplicate", "novel", "contradiction"})


@dataclass(frozen=True)
class MaintenanceCase:
    """One labeled maintenance decision: what the loop should do with a source."""

    id: str
    kind: str
    title: str
    body: str
    target: str | None
    expected_action: str


def load_queries(path: Path) -> tuple[BenchQuery, ...]:
    """Load the held-out query set from a JSONL file."""
    queries: list[BenchQuery] = []
    for record in _read_jsonl(path):
        queries.append(
            BenchQuery(
                id=_require_str(record, "id"),
                question=_require_str(record, "question"),
                required_concepts=tuple(_require_str_list(record, "required_concepts")),
                answer_keywords=tuple(_require_str_list(record, "answer_keywords")),
            )
        )
    return tuple(queries)


def load_maintenance(path: Path) -> tuple[MaintenanceCase, ...]:
    """Load the held-out maintenance cases from a JSONL file."""
    cases: list[MaintenanceCase] = []
    for record in _read_jsonl(path):
        kind = _require_str(record, "kind")
        if kind not in MAINTENANCE_KINDS:
            raise ValueError(f"maintenance kind must be one of {sorted(MAINTENANCE_KINDS)}: {kind}")
        action = _require_str(record, "expected_action")
        if action not in MAINTENANCE_ACTIONS:
            raise ValueError(
                f"expected_action must be one of {sorted(MAINTENANCE_ACTIONS)}: {action}"
            )
        target = _require_str(record, "target")
        cases.append(
            MaintenanceCase(
                id=_require_str(record, "id"),
                kind=kind,
                title=_require_str(record, "title"),
                body=_require_str(record, "body"),
                target=target or None,
                expected_action=action,
            )
        )
    return tuple(cases)


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        parsed = json.loads(stripped)
        if not isinstance(parsed, dict):
            raise ValueError(f"{path}:{line_number}: each line must be a JSON object")
        records.append(parsed)
    return records


def _require_str(record: dict[str, object], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str):
        raise ValueError(f"field {key!r} must be a string, got {type(value).__name__}")
    return value


def _require_str_list(record: dict[str, object], key: str) -> list[str]:
    value = record.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"field {key!r} must be a list of strings")
    return [item for item in value if isinstance(item, str)]
