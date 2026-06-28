"""Claim-level temporal validity: effective dating + current filter (M9 PR-1)."""

from __future__ import annotations

from datetime import UTC, datetime

from kosha.contradiction import effective_claims, in_force
from kosha.merge.claims import make_claim, supersede_claim
from kosha.model import ClaimStatus

_Q1 = datetime(2026, 1, 1, tzinfo=UTC)
_Q2 = datetime(2026, 4, 1, tzinfo=UTC)
_Q3 = datetime(2026, 7, 1, tzinfo=UTC)

_RETURNS = "Standard returns are accepted within 30 days of delivery."
_GOLD = "Gold members receive free return shipping."


def test_make_claim_carries_effective_window() -> None:
    claim = make_claim(_RETURNS, "s1", _Q1, effective_from=_Q1, effective_to=_Q3)
    assert claim.effective_from == _Q1
    assert claim.effective_to == _Q3


def test_make_claim_defaults_open_ended() -> None:
    claim = make_claim(_RETURNS, "s1", _Q1)
    assert claim.effective_from is None
    assert claim.effective_to is None


def test_in_force_current_view_is_open_ended_only() -> None:
    open_claim = make_claim(_RETURNS, "s1", _Q1, effective_from=_Q1)
    expired = make_claim(_RETURNS, "s1", _Q1, effective_from=_Q1, effective_to=_Q2)
    # asof=None is the "what is the policy now" view: effective_to is None.
    assert in_force(open_claim) is True
    assert in_force(expired) is False


def test_in_force_window_is_half_open() -> None:
    claim = make_claim(_RETURNS, "s1", _Q1, effective_from=_Q1, effective_to=_Q3)
    assert in_force(claim, _Q1) is True  # start is inclusive
    assert in_force(claim, _Q2) is True  # inside the window
    assert in_force(claim, _Q3) is False  # end is exclusive
    before = datetime(2025, 12, 1, tzinfo=UTC)
    assert in_force(claim, before) is False


def test_in_force_unbounded_window_always_holds() -> None:
    claim = make_claim(_RETURNS, "s1", _Q1)
    assert in_force(claim, _Q1) is True
    assert in_force(claim, _Q3) is True


def test_effective_claims_drops_expired_and_superseded() -> None:
    open_claim = make_claim(_GOLD, "s1", _Q1, effective_from=_Q1)
    expired = make_claim(_RETURNS, "s1", _Q1, effective_from=_Q1, effective_to=_Q2)
    current = effective_claims([open_claim, expired])
    assert [c.claim_id for c in current] == [open_claim.claim_id]


def test_effective_claims_excludes_retired_chain_head() -> None:
    root = make_claim(_RETURNS, "s1", _Q1, effective_from=_Q1)
    claims, replacement = supersede_claim(
        [root],
        root.claim_id,
        statement="Standard returns are accepted within 60 days of delivery.",
        source_id="s2",
        asserted_at=_Q2,
    )
    # current_claims already drops the superseded root; the live head surfaces.
    current = effective_claims(claims)
    assert [c.claim_id for c in current] == [replacement.claim_id]
    assert any(c.status is ClaimStatus.SUPERSEDED for c in claims)


def test_effective_claims_asof_selects_the_window_in_force_then() -> None:
    q1_claim = make_claim(_RETURNS, "s1", _Q1, effective_from=_Q1, effective_to=_Q3)
    # A single in-force claim with a closed window: visible inside, gone after.
    assert effective_claims([q1_claim], asof=_Q2) == [q1_claim]
    assert effective_claims([q1_claim], asof=_Q3) == []
