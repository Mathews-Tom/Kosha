"""Contradiction-resolution policy: temporal-first then authority (M9 PR-3)."""

from __future__ import annotations

from datetime import UTC, datetime

from kosha.contradiction.policy import Resolution, resolve_conflict
from kosha.merge.claims import make_claim
from kosha.model import Claim

_Q1 = datetime(2026, 1, 1, tzinfo=UTC)
_Q3 = datetime(2026, 7, 1, tzinfo=UTC)

_RETURNS_30 = "Standard returns are accepted within 30 days of delivery."
_RETURNS_60 = "Standard returns are accepted within 60 days of delivery."


def _claim(statement: str, source_id: str, *, effective_from: datetime | None = None) -> Claim:
    return make_claim(statement, source_id, _Q1, effective_from=effective_from)


def test_later_effective_from_supersedes() -> None:
    old = _claim(_RETURNS_30, "wiki", effective_from=_Q1)
    new = _claim(_RETURNS_60, "wiki", effective_from=_Q3)
    outcome = resolve_conflict(old, new, old_authority=1, new_authority=1)
    assert outcome.resolution is Resolution.TEMPORAL
    assert outcome.winner == "new"


def test_new_dated_supersedes_undated_old() -> None:
    old = _claim(_RETURNS_30, "wiki", effective_from=None)
    new = _claim(_RETURNS_60, "wiki", effective_from=_Q3)
    outcome = resolve_conflict(old, new, old_authority=1, new_authority=1)
    assert outcome.resolution is Resolution.TEMPORAL


def test_temporal_beats_authority_even_when_old_outranks_new() -> None:
    # A dated policy change is a new version: it wins even from a lower-authority
    # source than the claim it replaces.
    old = _claim(_RETURNS_30, "official", effective_from=_Q1)
    new = _claim(_RETURNS_60, "chat", effective_from=_Q3)
    outcome = resolve_conflict(old, new, old_authority=3, new_authority=1)
    assert outcome.resolution is Resolution.TEMPORAL
    assert outcome.winner == "new"


def test_higher_authority_new_wins_without_temporal_ordering() -> None:
    old = _claim(_RETURNS_30, "wiki")
    new = _claim(_RETURNS_60, "official")
    outcome = resolve_conflict(old, new, old_authority=1, new_authority=3)
    assert outcome.resolution is Resolution.AUTHORITY
    assert outcome.winner == "new"


def test_higher_authority_old_wins() -> None:
    old = _claim(_RETURNS_30, "official")
    new = _claim(_RETURNS_60, "chat")
    outcome = resolve_conflict(old, new, old_authority=3, new_authority=1)
    assert outcome.resolution is Resolution.AUTHORITY
    assert outcome.winner == "old"


def test_backdated_new_does_not_win_temporally() -> None:
    # New effective_from is earlier than old's: not a later version, so temporal
    # does not apply; equal authority then escalates.
    old = _claim(_RETURNS_30, "wiki", effective_from=_Q3)
    new = _claim(_RETURNS_60, "wiki", effective_from=_Q1)
    outcome = resolve_conflict(old, new, old_authority=2, new_authority=2)
    assert outcome.resolution is Resolution.ESCALATE


def test_equal_authority_overlapping_validity_escalates() -> None:
    old = _claim(_RETURNS_30, "wiki-a")
    new = _claim(_RETURNS_60, "wiki-b")
    outcome = resolve_conflict(old, new, old_authority=2, new_authority=2)
    assert outcome.resolution is Resolution.ESCALATE
    assert outcome.winner is None
    assert outcome.escalated is True


def test_same_effective_from_falls_through_to_authority() -> None:
    old = _claim(_RETURNS_30, "wiki", effective_from=_Q1)
    new = _claim(_RETURNS_60, "official", effective_from=_Q1)
    outcome = resolve_conflict(old, new, old_authority=1, new_authority=3)
    assert outcome.resolution is Resolution.AUTHORITY
    assert outcome.winner == "new"
