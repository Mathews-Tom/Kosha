"""Reconcile + escalation lane + never-overwrite invariant (M9 PR-4)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from kosha.contradiction.detect import LexicalContradictionJudge
from kosha.contradiction.escalate import (
    SilentOverwriteError,
    assert_no_silent_overwrite,
    reconcile,
)
from kosha.contradiction.policy import Resolution
from kosha.merge.claims import current_claims, make_claim
from kosha.model import ClaimStatus

_Q1 = datetime(2026, 1, 1, tzinfo=UTC)
_Q3 = datetime(2026, 7, 1, tzinfo=UTC)
_JUDGE = LexicalContradictionJudge()

_RETURNS_30 = "Standard returns are accepted within 30 days of delivery."
_RETURNS_60 = "Standard returns are accepted within 60 days of delivery."
_GOLD_FREE = "Gold members receive free return shipping."
_REFUNDS = "Refunds post to the original payment card after approval."


def test_compatible_addition_appends_without_conflict() -> None:
    old = [make_claim(_RETURNS_30, "wiki", _Q1)]
    new = make_claim(_REFUNDS, "wiki", _Q1)
    result = reconcile(old, new, authority={"wiki": 1}, judge=_JUDGE)
    assert result.conflicting is False
    assert result.outcome is None
    assert [c.statement for c in current_claims(result.claims)] == [_RETURNS_30, _REFUNDS]
    assert_no_silent_overwrite(old, result.claims)


def test_temporal_supersede_closes_old_window_and_promotes_new() -> None:
    old = [make_claim(_RETURNS_30, "wiki", _Q1, effective_from=_Q1)]
    new = make_claim(_RETURNS_60, "wiki", _Q3, effective_from=_Q3)
    result = reconcile(old, new, authority={"wiki": 1}, judge=_JUDGE)
    assert result.outcome is not None
    assert result.outcome.resolution is Resolution.TEMPORAL
    superseded = next(c for c in result.claims if c.claim_id == old[0].claim_id)
    assert superseded.status is ClaimStatus.SUPERSEDED
    assert superseded.effective_to == _Q3  # old retained, window closed at handover
    heads = current_claims(result.claims)
    assert [c.statement for c in heads] == [_RETURNS_60]
    assert_no_silent_overwrite(old, result.claims)


def test_higher_authority_new_marks_old_contradicted() -> None:
    old = [make_claim(_RETURNS_30, "wiki", _Q1)]
    new = make_claim(_RETURNS_60, "official", _Q1)
    result = reconcile(old, new, authority={"wiki": 1, "official": 3}, judge=_JUDGE)
    assert result.outcome is not None
    assert result.outcome.resolution is Resolution.AUTHORITY
    loser = next(c for c in result.claims if c.claim_id == old[0].claim_id)
    assert loser.status is ClaimStatus.CONTRADICTED
    assert [c.statement for c in current_claims(result.claims)] == [_RETURNS_60]
    assert_no_silent_overwrite(old, result.claims)


def test_higher_authority_old_retains_new_as_contradicted() -> None:
    old = [make_claim(_RETURNS_30, "official", _Q1)]
    new = make_claim(_RETURNS_60, "chat", _Q1)
    result = reconcile(old, new, authority={"official": 3, "chat": 1}, judge=_JUDGE)
    assert result.outcome is not None
    assert result.outcome.winner == "old"
    # Old keeps in force; the rejected new claim is retained, not dropped.
    assert [c.statement for c in current_claims(result.claims)] == [_RETURNS_30]
    new_in_list = next(c for c in result.claims if c.claim_id == new.claim_id)
    assert new_in_list.status is ClaimStatus.CONTRADICTED
    assert result.escalated is False
    assert_no_silent_overwrite(old, result.claims)


def test_equal_authority_overlap_escalates_and_holds_new() -> None:
    old = [make_claim(_RETURNS_30, "wiki-a", _Q1)]
    new = make_claim(_RETURNS_60, "wiki-b", _Q1)
    result = reconcile(old, new, authority={"wiki-a": 2, "wiki-b": 2}, judge=_JUDGE)
    assert result.outcome is not None
    assert result.outcome.resolution is Resolution.ESCALATE
    assert result.escalated is True
    assert result.escalation is not None
    assert result.escalation.old_claim.claim_id == old[0].claim_id
    assert result.escalation.new_claim.claim_id == new.claim_id
    # Nothing auto-applied: old stays current, new held as contradicted.
    assert [c.statement for c in current_claims(result.claims)] == [_RETURNS_30]
    held = next(c for c in result.claims if c.claim_id == new.claim_id)
    assert held.status is ClaimStatus.CONTRADICTED
    assert_no_silent_overwrite(old, result.claims)


def test_unknown_source_defaults_to_zero_authority_and_escalates() -> None:
    old = [make_claim(_RETURNS_30, "unranked-a", _Q1)]
    new = make_claim(_RETURNS_60, "unranked-b", _Q1)
    result = reconcile(old, new, authority={}, judge=_JUDGE)
    assert result.outcome is not None
    assert result.outcome.resolution is Resolution.ESCALATE


def test_assert_no_silent_overwrite_detects_a_dropped_claim() -> None:
    before = [make_claim(_RETURNS_30, "wiki", _Q1), make_claim(_GOLD_FREE, "wiki", _Q1)]
    after = [before[0]]
    with pytest.raises(SilentOverwriteError, match="dropped"):
        assert_no_silent_overwrite(before, after)


def test_assert_no_silent_overwrite_detects_an_in_place_rewrite() -> None:
    before = [make_claim(_RETURNS_30, "wiki", _Q1)]
    after = [before[0].model_copy(update={"statement": _RETURNS_60})]
    with pytest.raises(SilentOverwriteError, match="rewritten"):
        assert_no_silent_overwrite(before, after)


def test_assert_no_silent_overwrite_allows_status_and_window_changes() -> None:
    before = [make_claim(_RETURNS_30, "wiki", _Q1, effective_from=_Q1)]
    after = [
        before[0].model_copy(
            update={"status": ClaimStatus.SUPERSEDED, "effective_to": _Q3}
        )
    ]
    assert_no_silent_overwrite(before, after)  # does not raise


def test_higher_authority_new_wins_links_old_via_contradicts() -> None:
    old = [make_claim(_RETURNS_30, "wiki", _Q1)]
    new = make_claim(_RETURNS_60, "official", _Q1)
    result = reconcile(old, new, authority={"wiki": 0, "official": 10}, judge=_JUDGE)
    loser = next(c for c in result.claims if c.claim_id == old[0].claim_id)
    assert loser.status is ClaimStatus.CONTRADICTED
    assert loser.contradicts == new.claim_id


def test_higher_authority_old_wins_links_new_via_contradicts() -> None:
    old = [make_claim(_RETURNS_30, "official", _Q1)]
    new = make_claim(_RETURNS_60, "wiki", _Q1)
    result = reconcile(old, new, authority={"official": 10, "wiki": 0}, judge=_JUDGE)
    loser = next(c for c in result.claims if c.claim_id == new.claim_id)
    assert loser.status is ClaimStatus.CONTRADICTED
    assert loser.contradicts == old[0].claim_id


def test_escalate_links_the_held_new_claim_via_contradicts() -> None:
    old = [make_claim(_RETURNS_30, "wiki-a", _Q1)]
    new = make_claim(_RETURNS_60, "wiki-b", _Q1)
    result = reconcile(old, new, authority={}, judge=_JUDGE)
    loser = next(c for c in result.claims if c.claim_id == new.claim_id)
    assert loser.status is ClaimStatus.CONTRADICTED
    assert loser.contradicts == old[0].claim_id
