"""Claim lineage: reconstruct supersede/contradiction history (M7 PR-1)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from kosha.contradiction.detect import LexicalContradictionJudge
from kosha.contradiction.escalate import reconcile
from kosha.merge.claims import make_claim, supersede_claim
from kosha.merge.lineage import claim_chain, concept_history, contested_by
from kosha.model import ClaimStatus

_T0 = datetime(2026, 1, 1, tzinfo=UTC)
_T1 = datetime(2026, 2, 1, tzinfo=UTC)
_T2 = datetime(2026, 3, 1, tzinfo=UTC)
_JUDGE = LexicalContradictionJudge()

_RETURNS_30 = "Standard returns are accepted within 30 days of delivery."
_RETURNS_45 = "Standard returns are accepted within 45 days of delivery."
_RETURNS_60 = "Standard returns are accepted within 60 days of delivery."
_GOLD = "Gold members receive free return shipping."


def _chain() -> tuple[list, str, str, str]:
    """Build a three-generation supersede chain: root -> mid -> head."""
    root = make_claim(_RETURNS_30, "wiki", _T0, reviewer="Ann")
    claims, mid = supersede_claim(
        [root], root.claim_id, statement=_RETURNS_45, source_id="wiki-v2", asserted_at=_T1,
        reviewer="Ben",
    )
    claims, head = supersede_claim(
        claims, mid.claim_id, statement=_RETURNS_60, source_id="wiki-v3", asserted_at=_T2,
        reviewer="Cara",
    )
    return claims, root.claim_id, mid.claim_id, head.claim_id


def test_concept_history_orders_chronologically_regardless_of_input_order() -> None:
    a = make_claim(_RETURNS_30, "s1", _T2)
    b = make_claim(_GOLD, "s1", _T0)
    history = concept_history([a, b])
    assert [entry.claim_id for entry in history] == [b.claim_id, a.claim_id]


def test_concept_history_entry_carries_full_provenance() -> None:
    claim = make_claim(_RETURNS_30, "wiki", _T0, citations=["doc-a"], reviewer="Ann")
    entry = concept_history([claim])[0]
    assert entry.statement == _RETURNS_30
    assert entry.source_id == "wiki"
    assert entry.asserted_at == _T0
    assert entry.reviewer == "Ann"
    assert entry.status is ClaimStatus.CURRENT
    assert entry.citations == ("doc-a",)
    assert entry.supersedes is None
    assert entry.contradicts is None


def test_claim_chain_from_the_root_returns_every_generation_oldest_first() -> None:
    claims, root_id, mid_id, head_id = _chain()
    chain = claim_chain(claims, root_id)
    assert [entry.claim_id for entry in chain] == [root_id, mid_id, head_id]
    assert [entry.status for entry in chain] == [
        ClaimStatus.SUPERSEDED,
        ClaimStatus.SUPERSEDED,
        ClaimStatus.CURRENT,
    ]


def test_claim_chain_from_a_middle_link_returns_the_same_full_chain() -> None:
    claims, root_id, mid_id, head_id = _chain()
    chain = claim_chain(claims, mid_id)
    assert [entry.claim_id for entry in chain] == [root_id, mid_id, head_id]


def test_claim_chain_from_the_head_returns_the_same_full_chain() -> None:
    claims, root_id, mid_id, head_id = _chain()
    chain = claim_chain(claims, head_id)
    assert [entry.claim_id for entry in chain] == [root_id, mid_id, head_id]


def test_claim_chain_reports_what_superseded_a_link_when_from_where_and_by_whom() -> None:
    claims, root_id, mid_id, _ = _chain()
    chain = claim_chain(claims, root_id)
    successor = next(entry for entry in chain if entry.claim_id == mid_id)
    assert successor.supersedes == root_id
    assert successor.asserted_at == _T1
    assert successor.source_id == "wiki-v2"
    assert successor.reviewer == "Ben"


def test_claim_chain_unknown_id_raises_key_error() -> None:
    claims, *_ = _chain()
    with pytest.raises(KeyError):
        claim_chain(claims, "no-such-claim")


def test_contested_by_finds_the_claim_rejected_against_a_winner() -> None:
    old = [make_claim(_RETURNS_30, "official", _T0)]
    new = make_claim(_RETURNS_60, "wiki", _T1, reviewer="Dee")
    result = reconcile(old, new, authority={"official": 10, "wiki": 0}, judge=_JUDGE)
    claims = list(result.claims)
    contested = contested_by(claims, old[0].claim_id)
    assert len(contested) == 1
    assert contested[0].claim_id == new.claim_id
    assert contested[0].status is ClaimStatus.CONTRADICTED
    assert contested[0].contradicts == old[0].claim_id
    assert contested[0].reviewer == "Dee"


def test_contested_by_finds_the_incumbent_when_the_new_claim_wins() -> None:
    old = [make_claim(_RETURNS_30, "wiki", _T0)]
    new = make_claim(_RETURNS_60, "official", _T1)
    result = reconcile(old, new, authority={"wiki": 0, "official": 10}, judge=_JUDGE)
    claims = list(result.claims)
    contested = contested_by(claims, new.claim_id)
    assert len(contested) == 1
    assert contested[0].claim_id == old[0].claim_id
    assert contested[0].status is ClaimStatus.CONTRADICTED


def test_contested_by_returns_nothing_for_an_uncontested_claim() -> None:
    claims = [make_claim(_RETURNS_30, "wiki", _T0)]
    assert contested_by(claims, claims[0].claim_id) == []
