"""KnowledgeGap contract invariants and lifecycle transitions (DEVELOPMENT_PLAN.md M10)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from kosha.gaps.model import GapKind, GapReasonCode, GapStatus, KnowledgeGap, dedup_key

_OPENED = datetime(2026, 7, 1, tzinfo=UTC)
_LATER = datetime(2026, 7, 5, tzinfo=UTC)


def _gap(**overrides: object) -> KnowledgeGap:
    fields: dict[str, object] = {
        "gap_id": dedup_key(GapKind.LEGACY_EVIDENCE, "deadbeef"),
        "kind": GapKind.LEGACY_EVIDENCE,
        "reason_code": GapReasonCode.MISSING_SOURCE_RUN_TRAILER,
        "opened_at": _OPENED,
        "last_seen_at": _OPENED,
    }
    fields.update(overrides)
    return KnowledgeGap.model_validate(fields)


def test_dedup_key_is_stable_for_the_same_kind_and_natural_key() -> None:
    a = dedup_key(GapKind.LEGACY_EVIDENCE, "abc123")
    b = dedup_key(GapKind.LEGACY_EVIDENCE, "abc123")
    assert a == b


def test_dedup_key_differs_across_kinds_for_the_same_natural_key() -> None:
    a = dedup_key(GapKind.LEGACY_EVIDENCE, "abc123")
    b = dedup_key(GapKind.INCOMPLETE_COVERAGE, "abc123")
    assert a != b


def test_dedup_key_differs_across_natural_keys() -> None:
    a = dedup_key(GapKind.LEGACY_EVIDENCE, "abc123")
    b = dedup_key(GapKind.LEGACY_EVIDENCE, "def456")
    assert a != b


def test_gap_id_must_be_a_64_hex_digest() -> None:
    with pytest.raises(ValidationError, match="gap_id"):
        _gap(gap_id="not-a-digest")


def test_last_seen_at_before_opened_at_is_rejected() -> None:
    with pytest.raises(ValidationError, match="last_seen_at"):
        _gap(opened_at=_LATER, last_seen_at=_OPENED)


def test_an_open_gap_defaults_to_status_open() -> None:
    gap = _gap()
    assert gap.status is GapStatus.OPEN
    assert gap.resolution_reference is None


def test_an_open_gap_with_a_resolution_reference_is_rejected() -> None:
    with pytest.raises(ValidationError, match="must not carry a resolution_reference"):
        _gap(resolution_reference="deadbeef")


def test_an_answered_gap_without_a_resolution_reference_is_rejected() -> None:
    with pytest.raises(ValidationError, match="requires a resolution_reference"):
        _gap(status=GapStatus.ANSWERED)


def test_an_invalidated_gap_without_a_resolution_reference_is_rejected() -> None:
    with pytest.raises(ValidationError, match="requires a resolution_reference"):
        _gap(status=GapStatus.INVALIDATED)


def test_a_credential_shaped_resolution_reference_is_rejected() -> None:
    with pytest.raises(ValidationError, match="secret detector"):
        _gap(
            status=GapStatus.ANSWERED,
            resolution_reference="api_key=abcdefghijklmnopqrstuvwx1234",
        )


def test_an_oversized_owner_is_rejected() -> None:
    with pytest.raises(ValidationError, match="500 chars"):
        _gap(owner="x" * 501)


# --- lifecycle transitions ----------------------------------------------------


def test_observe_bumps_last_seen_at_and_seen_count() -> None:
    gap = _gap()
    observed = gap.observe(
        at=_LATER, source_run_ids=(), evidence_sha256=(), affected_concept_ids=()
    )
    assert observed.last_seen_at == _LATER
    assert observed.seen_count == 2
    assert observed.status is GapStatus.OPEN


def test_observe_unions_new_source_runs_evidence_and_concepts_without_duplicating() -> None:
    gap = _gap(
        source_run_ids=("run-1",),
        evidence_sha256=("a" * 64,),
        affected_concept_ids=("policies/a.md",),
    )
    observed = gap.observe(
        at=_LATER,
        source_run_ids=("run-1", "run-2"),
        evidence_sha256=("a" * 64, "b" * 64),
        affected_concept_ids=("policies/a.md", "policies/b.md"),
    )
    assert observed.source_run_ids == ("run-1", "run-2")
    assert observed.evidence_sha256 == ("a" * 64, "b" * 64)
    assert observed.affected_concept_ids == ("policies/a.md", "policies/b.md")


def test_observe_cannot_move_last_seen_at_backward() -> None:
    gap = _gap(last_seen_at=_LATER)
    with pytest.raises(ValueError, match="cannot move last_seen_at backward"):
        gap.observe(at=_OPENED, source_run_ids=(), evidence_sha256=(), affected_concept_ids=())


def test_observe_on_a_terminal_gap_updates_history_without_changing_status() -> None:
    gap = _gap().answer(resolution_reference="c" * 64, at=_LATER)
    observed = gap.observe(
        at=datetime(2026, 7, 10, tzinfo=UTC),
        source_run_ids=(),
        evidence_sha256=(),
        affected_concept_ids=(),
    )
    assert observed.status is GapStatus.ANSWERED
    assert observed.seen_count == 2


def test_answer_transitions_open_to_answered_with_resolution() -> None:
    gap = _gap()
    answered = gap.answer(resolution_reference="c" * 64, at=_LATER)
    assert answered.status is GapStatus.ANSWERED
    assert answered.resolution_reference == "c" * 64
    assert answered.last_seen_at == _LATER


def test_invalidate_transitions_open_to_invalidated_with_resolution() -> None:
    gap = _gap()
    invalidated = gap.invalidate(resolution_reference="reviewed: false positive", at=_LATER)
    assert invalidated.status is GapStatus.INVALIDATED
    assert invalidated.resolution_reference == "reviewed: false positive"


def test_mark_stale_transitions_open_to_stale_without_a_resolution() -> None:
    gap = _gap()
    stale = gap.mark_stale(at=_LATER)
    assert stale.status is GapStatus.STALE
    assert stale.resolution_reference is None


def test_mark_stale_on_a_non_open_gap_fails_loud() -> None:
    gap = _gap().answer(resolution_reference="c" * 64, at=_LATER)
    with pytest.raises(ValueError, match="only an open gap may be marked stale"):
        gap.mark_stale(at=_LATER)


def test_answering_an_already_answered_gap_fails_loud_never_re_resolves() -> None:
    gap = _gap().answer(resolution_reference="c" * 64, at=_LATER)
    with pytest.raises(ValueError, match="already 'answered'"):
        gap.answer(resolution_reference="d" * 64, at=datetime(2026, 7, 10, tzinfo=UTC))


def test_invalidating_an_answered_gap_fails_loud() -> None:
    gap = _gap().answer(resolution_reference="c" * 64, at=_LATER)
    with pytest.raises(ValueError, match="already 'answered'"):
        gap.invalidate(resolution_reference="d" * 64, at=datetime(2026, 7, 10, tzinfo=UTC))


def test_answering_a_stale_gap_fails_loud_stale_history_is_retained_not_reopened() -> None:
    gap = _gap().mark_stale(at=_LATER)
    with pytest.raises(ValueError, match="already 'stale'"):
        gap.answer(resolution_reference="c" * 64, at=datetime(2026, 7, 10, tzinfo=UTC))
