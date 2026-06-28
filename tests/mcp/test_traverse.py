"""find_concepts (embedding jump) and follow_links (graph traversal)."""

from __future__ import annotations

from kosha.mcp.service import KoshaKnowledgeService

_GOLD = "policies/returns/gold-members"
_QUERY = "how long does a gold member have to return an item"


def test_find_concepts_jumps_into_the_returns_neighborhood(
    service: KoshaKnowledgeService,
) -> None:
    view = service.find_concepts(_QUERY, k=3)
    ids = [candidate["concept_id"] for candidate in view["candidates"]]
    assert len(view["candidates"]) == 3
    assert "policies/returns/standard" in ids


def test_find_concepts_returns_descriptions_not_bodies(
    service: KoshaKnowledgeService,
) -> None:
    view = service.find_concepts("returns", k=2)
    for candidate in view["candidates"]:
        assert set(candidate.keys()) == {"concept_id", "score", "description"}
        assert candidate["concept_id"] in service.bundle.concepts


def test_jump_then_links_reach_the_answer_concept(
    service: KoshaKnowledgeService,
) -> None:
    # The hybrid path: the raw jump lands near (standard returns), then traversal
    # expands to the gold-specific concept the jump alone missed.
    seeds = [c["concept_id"] for c in service.find_concepts(_QUERY, k=3)["candidates"]]
    reachable = set(seeds)
    for concept_id in seeds:
        neighborhood = service.follow_links(concept_id)
        reachable |= {link["concept_id"] for link in neighborhood["out_links"]}
        reachable |= {link["concept_id"] for link in neighborhood["backlinks"]}
    assert _GOLD not in seeds
    assert _GOLD in reachable


def test_follow_links_lists_out_links_with_descriptions(
    service: KoshaKnowledgeService,
) -> None:
    view = service.follow_links(_GOLD)
    out = {link["concept_id"]: link for link in view["out_links"]}
    assert {"entities/membership-tier", "policies/returns/standard", "policies/refunds"} <= set(
        out
    )
    assert all(link["present"] for link in view["out_links"])
    assert out["entities/membership-tier"]["description"]


def test_follow_links_computes_backlinks(service: KoshaKnowledgeService) -> None:
    view = service.follow_links("policies/returns/standard")
    backlinks = {link["concept_id"] for link in view["backlinks"]}
    assert _GOLD in backlinks
