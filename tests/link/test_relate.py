"""Relate surface: discovery, ranking, and parsing (M8 PR-1)."""

from __future__ import annotations

from collections.abc import Sequence

from kosha.link import (
    GenerationRelator,
    LexicalRelator,
    Relation,
    build_relate_prompt,
    discover_relations,
    parse_relations,
)
from kosha.model import Bundle, Concept, Frontmatter
from kosha.providers.base import Generation, Usage


def _concept(
    concept_id: str,
    *,
    title: str,
    description: str = "",
    body: str = "",
    tags: list[str] | None = None,
    links: list[str] | None = None,
) -> Concept:
    return Concept(
        concept_id=concept_id,
        frontmatter=Frontmatter(
            type="Concept", title=title, description=description, tags=tags or []
        ),
        body=body,
        out_links=links or [],
    )


def _bundle(*concepts: Concept) -> Bundle:
    return Bundle(root_path="/tmp/b", concepts={c.concept_id: c for c in concepts})


_RETURNS = _concept(
    "policies/returns",
    title="Returns",
    description="Customers may return unworn items within the return window.",
    body="A return is accepted when the item is unworn and inside the return window.",
    tags=["returns"],
)
_REFUNDS = _concept(
    "policies/refunds",
    title="Refunds",
    description="A refund is issued to the original payment card after a return is approved.",
    body="Refunds for an approved return post to the original payment card.",
    tags=["returns"],
)
_SHIPPING = _concept(
    "logistics/shipping",
    title="Shipping carriers",
    description="Parcel carriers, transit windows, and freight surcharges by region.",
    body="Carriers move parcels across regions with freight surcharges.",
    tags=["logistics"],
)


def test_lexical_relator_relates_overlapping_concepts() -> None:
    related = LexicalRelator().relate(_RETURNS, [_REFUNDS, _SHIPPING])
    assert "policies/refunds" in related


def test_lexical_relator_skips_below_threshold() -> None:
    # Shipping shares no terms or tags with returns/refunds.
    related = LexicalRelator(threshold=0.2).relate(_SHIPPING, [_RETURNS, _REFUNDS])
    assert related == []


def test_lexical_relator_caps_and_ranks_by_score() -> None:
    relator = LexicalRelator(threshold=0.0, max_links=2)
    related = relator.relate(_RETURNS, [_REFUNDS, _SHIPPING])
    assert len(related) == 2
    # The strongest overlap (refunds) ranks ahead of the weak one.
    assert related[0] == "policies/refunds"


def test_lexical_relator_excludes_self() -> None:
    assert _RETURNS.concept_id not in LexicalRelator(threshold=0.0).relate(
        _RETURNS, [_RETURNS, _REFUNDS]
    )


def test_discover_relations_is_deterministic_and_new_only() -> None:
    bundle = _bundle(_RETURNS, _REFUNDS, _SHIPPING)
    first = discover_relations(bundle, LexicalRelator())
    second = discover_relations(bundle, LexicalRelator())
    assert first == second
    assert Relation(source="policies/returns", target="policies/refunds") in first


def test_discover_relations_skips_existing_out_links() -> None:
    returns = _concept(
        "policies/returns",
        title="Returns",
        description=_RETURNS.frontmatter.description or "",
        body=_RETURNS.body,
        tags=["returns"],
        links=["policies/refunds"],
    )
    bundle = _bundle(returns, _REFUNDS, _SHIPPING)
    relations = discover_relations(bundle, LexicalRelator())
    assert all(
        not (r.source == "policies/returns" and r.target == "policies/refunds") for r in relations
    )


def test_parse_relations_maps_indices_to_ids() -> None:
    candidates = [_REFUNDS, _SHIPPING]
    assert parse_relations("1, 2", candidates) == ["policies/refunds", "logistics/shipping"]
    assert parse_relations("only number 2 applies", candidates) == ["logistics/shipping"]


def test_parse_relations_handles_none_and_out_of_range() -> None:
    candidates = [_REFUNDS]
    assert parse_relations("none", candidates) == []
    assert parse_relations("5", candidates) == []
    assert parse_relations("1 1 1", candidates) == ["policies/refunds"]


class _StubProvider:
    """A generation provider that echoes a fixed answer for the relate prompt."""

    def __init__(self, answer: str) -> None:
        self._answer = answer

    @property
    def name(self) -> str:
        return "stub"

    def generate(self, query: str, context: str) -> Generation:
        return Generation(text=self._answer, usage=Usage(prompt_tokens=0, completion_tokens=0))


def test_generation_relator_parses_provider_choice() -> None:
    relator = GenerationRelator(_StubProvider("1"))
    related = relator.relate(_RETURNS, [_REFUNDS, _SHIPPING])
    assert related == ["policies/refunds"]


def test_build_relate_prompt_numbers_candidates() -> None:
    candidates: Sequence[Concept] = [_REFUNDS, _SHIPPING]
    query, context = build_relate_prompt(_RETURNS, candidates)
    assert "Returns" in query
    assert context.splitlines()[0].startswith("1. Refunds")
    assert context.splitlines()[1].startswith("2. Shipping carriers")
