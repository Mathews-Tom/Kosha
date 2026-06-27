"""Claim supersede + body projection: the core edit-drift guard (M7 PR-1)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from kosha.merge import current_claims, make_claim, mint_claim_id, render_body, supersede_claim
from kosha.model import ClaimStatus

_T0 = datetime(2026, 1, 1, tzinfo=UTC)
_T1 = datetime(2026, 2, 1, tzinfo=UTC)
_T2 = datetime(2026, 3, 1, tzinfo=UTC)

_RETURNS = "Standard returns are accepted within 30 days of delivery."
_GOLD = "Gold members receive free return shipping."


def _two_claim_body() -> list:
    return [
        make_claim(_RETURNS, "s1", _T0, citations=["s1"]),
        make_claim(_GOLD, "s2", _T0, citations=["s2"]),
    ]


def test_make_claim_is_current_and_content_addressed() -> None:
    claim = make_claim(_RETURNS, "s1", _T0)
    assert claim.status is ClaimStatus.CURRENT
    assert claim.supersedes is None
    assert claim.claim_id == mint_claim_id(_RETURNS, "s1", _T0)


def test_mint_id_differs_by_statement_source_and_time() -> None:
    base = mint_claim_id(_RETURNS, "s1", _T0)
    assert base != mint_claim_id(_GOLD, "s1", _T0)
    assert base != mint_claim_id(_RETURNS, "s2", _T0)
    assert base != mint_claim_id(_RETURNS, "s1", _T1)


def test_supersede_retires_target_and_links_replacement() -> None:
    claims = _two_claim_body()
    target = claims[0].claim_id
    updated, replacement = supersede_claim(
        claims,
        target,
        statement="Standard returns are accepted within 60 days of delivery.",
        source_id="s3",
        asserted_at=_T1,
        citations=["s3"],
    )
    retired = next(c for c in updated if c.claim_id == target)
    assert retired.status is ClaimStatus.SUPERSEDED
    assert replacement.status is ClaimStatus.CURRENT
    assert replacement.supersedes == target
    # History is retained, not deleted: old + new + the untouched second claim.
    assert len(updated) == 3


def test_supersede_only_affects_the_targeted_claim() -> None:
    claims = _two_claim_body()
    gold = claims[1]
    updated, _ = supersede_claim(
        claims,
        claims[0].claim_id,
        statement="Standard returns are accepted within 60 days of delivery.",
        source_id="s3",
        asserted_at=_T1,
    )
    # The unrelated claim object is carried through byte-identical.
    survivor = next(c for c in updated if c.claim_id == gold.claim_id)
    assert survivor == gold
    assert survivor.status is ClaimStatus.CURRENT


def test_current_claims_returns_heads_in_chain_order() -> None:
    claims = _two_claim_body()
    updated, replacement = supersede_claim(
        claims,
        claims[0].claim_id,
        statement="Standard returns are accepted within 60 days of delivery.",
        source_id="s3",
        asserted_at=_T1,
    )
    heads = current_claims(updated)
    # Replacement takes the retired claim's slot; the gold claim keeps position 2.
    assert [c.claim_id for c in heads] == [replacement.claim_id, claims[1].claim_id]


def test_render_body_leaves_unrelated_text_intact_on_supersede() -> None:
    claims = _two_claim_body()
    before = render_body(claims)
    assert _RETURNS in before and _GOLD in before

    new_returns = "Standard returns are accepted within 60 days of delivery."
    updated, _ = supersede_claim(
        claims, claims[0].claim_id, statement=new_returns, source_id="s3", asserted_at=_T1
    )
    after = render_body(updated)
    # The superseded statement is gone from the body; the new one is present.
    assert _RETURNS not in after
    assert new_returns in after
    # The unrelated claim's text is byte-for-byte unchanged.
    assert _GOLD in after


def test_render_body_aggregates_citations_without_duplicates() -> None:
    claims = [
        make_claim(_RETURNS, "s1", _T0, citations=["doc-a"]),
        make_claim(_GOLD, "s2", _T0, citations=["doc-a", "doc-b"]),
    ]
    body = render_body(claims)
    assert "# Citations" in body
    assert body.count("doc-a") == 1
    assert "doc-b" in body


def test_render_body_excludes_superseded_chain_with_no_live_head() -> None:
    claims = [make_claim(_RETURNS, "s1", _T0)]
    # Mark the only claim superseded with no replacement: a deletion, rendered empty.
    retired = [claims[0].model_copy(update={"status": ClaimStatus.SUPERSEDED})]
    assert current_claims(retired) == []
    assert render_body(retired) == ""


def test_supersede_rejects_non_current_target() -> None:
    claims = _two_claim_body()
    updated, _ = supersede_claim(
        claims, claims[0].claim_id, statement="x", source_id="s3", asserted_at=_T1
    )
    # The now-superseded claim cannot be superseded again.
    with pytest.raises(ValueError, match="non-current"):
        supersede_claim(
            updated, claims[0].claim_id, statement="y", source_id="s4", asserted_at=_T2
        )


def test_supersede_rejects_unknown_claim() -> None:
    with pytest.raises(KeyError):
        supersede_claim(
            _two_claim_body(), "nope", statement="x", source_id="s3", asserted_at=_T1
        )
