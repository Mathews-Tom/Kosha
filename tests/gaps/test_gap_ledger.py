"""GapLedgerStore: dedup merge, atomic persistence, lifecycle actions (DEVELOPMENT_PLAN.md M10)."""

from __future__ import annotations

import json
import os
import stat
from datetime import UTC, datetime
from pathlib import Path

import pytest

from kosha.gaps.ledger import GapLedgerCorruptionError, GapLedgerStore, UnknownGapError
from kosha.gaps.model import GapKind, GapReasonCode, GapStatus, KnowledgeGap, dedup_key
from kosha.gaps.paths import ledger_path

_T1 = datetime(2026, 7, 1, tzinfo=UTC)
_T2 = datetime(2026, 7, 5, tzinfo=UTC)
_T3 = datetime(2026, 7, 10, tzinfo=UTC)


def _event(natural_key: str, *, at: datetime, concept_id: str = "policies/a.md") -> KnowledgeGap:
    return KnowledgeGap(
        gap_id=dedup_key(GapKind.LEGACY_EVIDENCE, natural_key),
        kind=GapKind.LEGACY_EVIDENCE,
        reason_code=GapReasonCode.MISSING_SOURCE_RUN_TRAILER,
        opened_at=at,
        last_seen_at=at,
        affected_concept_ids=(concept_id,),
    )


def test_load_on_an_unwritten_ledger_returns_empty(tmp_path: Path) -> None:
    store = GapLedgerStore(tmp_path / "gaps")
    assert store.load() == ()


def test_merge_events_inserts_a_never_seen_gap_as_open(tmp_path: Path) -> None:
    store = GapLedgerStore(tmp_path / "gaps")
    event = _event("commit-1", at=_T1)

    merged = store.merge_events((event,))

    assert len(merged) == 1
    assert merged[0].gap_id == event.gap_id
    assert merged[0].status is GapStatus.OPEN
    assert merged[0].seen_count == 1


def test_merge_events_deduplicates_a_repeated_event_into_one_gap(tmp_path: Path) -> None:
    store = GapLedgerStore(tmp_path / "gaps")
    store.merge_events((_event("commit-1", at=_T1),))

    merged = store.merge_events((_event("commit-1", at=_T2),))

    assert len(merged) == 1
    assert merged[0].seen_count == 2
    assert merged[0].last_seen_at == _T2


def test_merge_events_across_two_categories_keeps_both_as_separate_gaps(tmp_path: Path) -> None:
    store = GapLedgerStore(tmp_path / "gaps")
    legacy = _event("commit-1", at=_T1)
    coverage = KnowledgeGap(
        gap_id=dedup_key(GapKind.INCOMPLETE_COVERAGE, "commit-2:policies/b.md"),
        kind=GapKind.INCOMPLETE_COVERAGE,
        reason_code=GapReasonCode.COVERAGE_WINDOWED,
        opened_at=_T1,
        last_seen_at=_T1,
        affected_concept_ids=("policies/b.md",),
    )

    merged = store.merge_events((legacy, coverage))

    assert {gap.kind for gap in merged} == {GapKind.LEGACY_EVIDENCE, GapKind.INCOMPLETE_COVERAGE}


def test_merge_events_rejects_a_non_open_event(tmp_path: Path) -> None:
    store = GapLedgerStore(tmp_path / "gaps")
    answered = _event("commit-1", at=_T1).answer(resolution_reference="c" * 64, at=_T2)
    with pytest.raises(ValueError, match="must be OPEN"):
        store.merge_events((answered,))


def test_save_writes_private_directory_and_file_permissions(tmp_path: Path) -> None:
    root = tmp_path / "gaps"
    store = GapLedgerStore(root)
    store.merge_events((_event("commit-1", at=_T1),))

    path = ledger_path(root)
    assert path.is_file()
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert stat.S_IMODE(root.stat().st_mode) == 0o700


def test_load_fails_loud_on_malformed_json(tmp_path: Path) -> None:
    root = tmp_path / "gaps"
    root.mkdir(parents=True)
    ledger_path(root).write_text("{not json", encoding="utf-8")
    store = GapLedgerStore(root)
    with pytest.raises(GapLedgerCorruptionError, match="malformed gap ledger"):
        store.load()


def test_load_fails_loud_on_a_non_array_ledger(tmp_path: Path) -> None:
    root = tmp_path / "gaps"
    root.mkdir(parents=True)
    ledger_path(root).write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    store = GapLedgerStore(root)
    with pytest.raises(GapLedgerCorruptionError, match="not a JSON array"):
        store.load()


def test_load_fails_loud_on_an_invalid_gap_record(tmp_path: Path) -> None:
    root = tmp_path / "gaps"
    root.mkdir(parents=True)
    ledger_path(root).write_text(json.dumps([{"gap_id": "nope"}]), encoding="utf-8")
    store = GapLedgerStore(root)
    with pytest.raises(GapLedgerCorruptionError, match="invalid gap record"):
        store.load()


# --- lifecycle actions ---------------------------------------------------------


def test_answer_transitions_a_stored_gap_and_persists_it(tmp_path: Path) -> None:
    store = GapLedgerStore(tmp_path / "gaps")
    event = _event("commit-1", at=_T1)
    store.merge_events((event,))

    answered = store.answer(event.gap_id, resolution_reference="c" * 64, at=_T2)

    assert answered.status is GapStatus.ANSWERED
    reloaded = store.load()
    assert reloaded[0].status is GapStatus.ANSWERED
    assert reloaded[0].resolution_reference == "c" * 64


def test_invalidate_transitions_a_stored_gap_and_persists_it(tmp_path: Path) -> None:
    store = GapLedgerStore(tmp_path / "gaps")
    event = _event("commit-1", at=_T1)
    store.merge_events((event,))

    invalidated = store.invalidate(event.gap_id, resolution_reference="not real", at=_T2)

    assert invalidated.status is GapStatus.INVALIDATED
    assert store.load()[0].status is GapStatus.INVALIDATED


def test_mark_stale_transitions_a_stored_gap_and_persists_it(tmp_path: Path) -> None:
    store = GapLedgerStore(tmp_path / "gaps")
    event = _event("commit-1", at=_T1)
    store.merge_events((event,))

    stale = store.mark_stale(event.gap_id, at=_T2)

    assert stale.status is GapStatus.STALE
    assert store.load()[0].status is GapStatus.STALE


def test_answer_on_an_unknown_gap_id_fails_loud(tmp_path: Path) -> None:
    store = GapLedgerStore(tmp_path / "gaps")
    with pytest.raises(UnknownGapError):
        store.answer("a" * 64, resolution_reference="c" * 64, at=_T1)


def test_terminal_gaps_are_retained_in_the_ledger_never_deleted(tmp_path: Path) -> None:
    store = GapLedgerStore(tmp_path / "gaps")
    open_event = _event("commit-1", at=_T1)
    store.merge_events((open_event,))
    store.answer(open_event.gap_id, resolution_reference="c" * 64, at=_T2)

    # A later scan re-observes the same underlying commit (unchanged history).
    merged = store.merge_events((_event("commit-1", at=_T3),))

    assert len(merged) == 1
    assert merged[0].status is GapStatus.ANSWERED  # not silently reopened
    assert merged[0].seen_count == 2  # but the recurrence is recorded
    assert merged[0].last_seen_at == _T3
