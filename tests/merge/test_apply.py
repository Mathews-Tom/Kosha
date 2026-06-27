"""Decision routing: dedup decision -> M7 writer (M7 PR-3)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from kosha.dedup import Action, Decision
from kosha.extract import ConceptDraft
from kosha.merge import LexicalClaimTargeter, apply_decision, create_concept
from kosha.model import ClaimStatus, Source, SourceKind

_T0 = datetime(2026, 1, 1, tzinfo=UTC)
_T1 = datetime(2026, 2, 1, tzinfo=UTC)

_RETURNS = "Standard returns are accepted within 30 days of delivery."


def _source(source_id: str) -> Source:
    return Source(source_id=source_id, kind=SourceKind.MARKDOWN, location=f"file://{source_id}.md")


def _draft(body: str, source_id: str = "s1") -> ConceptDraft:
    return ConceptDraft(
        title="Returns", body=body, description="Returns.", type="policy", source_id=source_id
    )


def _existing():
    return create_concept(_draft(_RETURNS), "policies/returns", _source("s1"), _T0)


def test_apply_update_routes_through_the_claim_merge() -> None:
    existing = _existing()
    decision = Decision(Action.UPDATE, "policies/returns", 0.97, "clear match")
    new = "Standard returns are accepted within 60 days of delivery."
    result = apply_decision(
        decision,
        _draft(new, "s2"),
        existing=existing,
        source=_source("s2"),
        asserted_at=_T1,
        targeter=LexicalClaimTargeter(),
    )
    assert new in result.body
    assert _RETURNS not in result.body
    retired = next(c for c in result.claims if c.statement == _RETURNS)
    assert retired.status is ClaimStatus.SUPERSEDED


def test_apply_create_mints_a_new_concept() -> None:
    decision = Decision(Action.CREATE, None, 0.02, "clearly novel")
    result = apply_decision(
        decision,
        _draft("Memberships renew annually.", "s3"),
        existing=None,
        source=_source("s3"),
        asserted_at=_T0,
        targeter=LexicalClaimTargeter(),
        new_concept_id="entities/membership",
    )
    assert result.concept_id == "entities/membership"
    assert "Memberships renew annually." in result.body


def test_apply_update_without_existing_raises() -> None:
    decision = Decision(Action.UPDATE, "policies/returns", 0.97, "match")
    with pytest.raises(ValueError, match="existing concept"):
        apply_decision(
            decision, _draft("x"), existing=None, source=_source("s2"),
            asserted_at=_T1, targeter=LexicalClaimTargeter(),
        )


def test_apply_create_without_new_id_raises() -> None:
    decision = Decision(Action.CREATE, None, 0.02, "novel")
    with pytest.raises(ValueError, match="new_concept_id"):
        apply_decision(
            decision, _draft("x"), existing=None, source=_source("s2"),
            asserted_at=_T1, targeter=LexicalClaimTargeter(),
        )


def test_apply_split_is_not_a_leaf_write() -> None:
    decision = Decision(Action.SPLIT, None, 0.5, "mixed", adjudicated=True)
    with pytest.raises(ValueError, match="resolve its parts"):
        apply_decision(
            decision, _draft("x"), existing=None, source=_source("s2"),
            asserted_at=_T1, targeter=LexicalClaimTargeter(),
        )
