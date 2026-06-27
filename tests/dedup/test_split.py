"""Tests for the granularity split branch and its re-resolve."""

from __future__ import annotations

from kosha.dedup.adjudicate import LexicalAdjudicator
from kosha.dedup.resolver import Action, resolve_draft
from kosha.dedup.split import make_splitter, split_draft
from kosha.extract import ConceptDraft
from kosha.index import EmbeddingIndex
from kosha.providers import ExtractiveGenerationProvider, LexicalEmbeddingProvider

_PROVIDER = LexicalEmbeddingProvider()
_GEN = ExtractiveGenerationProvider()

# Nine distinct sections -> over the granularity lint's 8-section ceiling.
_OVERSCOPED = (
    "# Returns\nUnworn items may be returned within 30 days.\n"
    "# Shipping\nStandard shipping takes 3-5 business days.\n"
    "# Refunds\nApproved refunds post to the original card.\n"
    "# Exchanges\nItems may be exchanged for another size.\n"
    "# Membership\nTiers are Standard, Silver, and Gold.\n"
    "# Orders\nAn order lists the purchased items.\n"
    "# Channels\nSupport is via email, chat, and phone.\n"
    "# Escalation\nUnresolved cases go to a supervisor.\n"
    "# Glossary\nDefines restocking fee and return window."
)
_CANDIDATE = "Returns and shipping policy overview for the store."


def _overscoped_draft() -> ConceptDraft:
    return ConceptDraft(
        title="Everything", body=_OVERSCOPED, description="", type="Policy", source_id="src://1"
    )


def _band_index() -> tuple[EmbeddingIndex, dict[str, str]]:
    entries = {"c0": _PROVIDER.embed([_CANDIDATE])[0]}
    return EmbeddingIndex(_PROVIDER, entries), {"c0": _CANDIDATE}


def test_split_draft_segments_and_inherits_provenance() -> None:
    parts = split_draft(_overscoped_draft(), _GEN)
    assert len(parts) == 9
    assert {p.title for p in parts} >= {"Returns", "Shipping", "Glossary"}
    assert all(p.source_id == "src://1" for p in parts)
    assert all(p.type == "Policy" for p in parts)


def test_split_draft_on_a_single_section_is_a_no_op() -> None:
    draft = ConceptDraft(
        title="One", body="# One\nA single atomic concept body.", description="",
        type="t", source_id="s",
    )
    parts = split_draft(draft, _GEN)
    assert len(parts) == 1


def test_resolver_split_branch_resegments_and_reresolves() -> None:
    index, texts = _band_index()
    decision = resolve_draft(
        _overscoped_draft(),
        index,
        texts,
        adjudicator=LexicalAdjudicator(),
        splitter=make_splitter(_GEN),
    )
    assert decision.action is Action.SPLIT
    assert decision.adjudicated is True
    assert len(decision.parts) == 9
    # Every re-resolved part is terminal (UPDATE/CREATE) — the depth guard
    # prevents a part from splitting again.
    assert all(p.action in {Action.UPDATE, Action.CREATE} for p in decision.parts)
    assert all(p.parts == () for p in decision.parts)


def test_split_verdict_without_a_splitter_is_a_leaf() -> None:
    index, texts = _band_index()
    decision = resolve_draft(
        _overscoped_draft(), index, texts, adjudicator=LexicalAdjudicator()
    )
    assert decision.action is Action.SPLIT
    assert decision.parts == ()
