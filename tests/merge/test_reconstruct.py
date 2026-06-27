"""Edit-drift guard: reconstruct-from-sources check (M7 PR-4)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from kosha.extract import ConceptDraft
from kosha.merge import (
    EditDriftError,
    LexicalClaimTargeter,
    assert_no_drift,
    create_concept,
    is_reconstructable,
    merge_update,
    reconstruct_from_sources,
    ungrounded_claims,
)
from kosha.model import Source, SourceKind

_T0 = datetime(2026, 1, 1, tzinfo=UTC)
_T1 = datetime(2026, 2, 1, tzinfo=UTC)

_RETURNS = "Standard returns are accepted within 30 days of delivery."
_GOLD = "Gold members receive free return shipping."
_RETURNS_60 = "Standard returns are accepted within 60 days of delivery."


def _source(source_id: str) -> Source:
    return Source(source_id=source_id, kind=SourceKind.MARKDOWN, location=f"file://{source_id}.md")


def _concept():
    draft = ConceptDraft(
        title="Returns",
        body=f"{_RETURNS}\n\n{_GOLD}",
        description="Returns.",
        type="policy",
        source_id="s1",
    )
    return create_concept(draft, "policies/returns", _source("s1"), _T0)


def test_assert_no_drift_accepts_a_projected_body() -> None:
    assert_no_drift(_concept())  # does not raise


def test_assert_no_drift_rejects_a_freehand_body_edit() -> None:
    tampered = _concept().model_copy(update={"body": "Hand-edited prose not in any claim."})
    with pytest.raises(EditDriftError, match="drifted"):
        assert_no_drift(tampered)


def test_concept_is_reconstructable_from_its_cited_sources() -> None:
    concept = _concept()
    sources = {"s1": f"intro\n{_RETURNS}\nmore\n{_GOLD}\n"}
    assert is_reconstructable(concept, sources)
    assert reconstruct_from_sources(concept, sources) == concept.body


def test_ungrounded_claim_is_flagged() -> None:
    concept = _concept()
    # s1 omits the gold claim -> it is ungrounded.
    sources = {"s1": f"intro {_RETURNS}"}
    missing = ungrounded_claims(concept, sources)
    assert [c.statement for c in missing] == [_GOLD]
    assert not is_reconstructable(concept, sources)
    with pytest.raises(EditDriftError, match="not reconstructable"):
        reconstruct_from_sources(concept, sources)


def test_superseded_claims_need_no_grounding() -> None:
    concept = _concept()
    updated = merge_update(
        concept,
        ConceptDraft(
            title="Returns", body=_RETURNS_60, description="Returns.", type="policy", source_id="s2"
        ),
        _source("s2"),
        _T1,
        targeter=LexicalClaimTargeter(),
    )
    # Only the live claims must be grounded; the retired 30-day claim's source is gone.
    sources = {"s2": _RETURNS_60, "s1": _GOLD}
    assert is_reconstructable(updated, sources)
    assert reconstruct_from_sources(updated, sources) == updated.body


def test_grounding_tolerates_whitespace_differences() -> None:
    concept = _concept()
    sources = {"s1": f"{_RETURNS}   \n\n   {_GOLD}"}
    assert is_reconstructable(concept, sources)
