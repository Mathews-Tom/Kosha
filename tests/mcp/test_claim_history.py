"""Claim lineage over the MCP consumer surface (M7 PR-2)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from kosha.mcp.service import ConceptNotFoundError, KoshaKnowledgeService
from kosha.model import Bundle, Claim, ClaimStatus
from kosha.okf.load import load_bundle

NORTHWIND = Path(__file__).resolve().parents[2] / "bundles" / "northwind"
GOLD = "policies/returns/gold-members"
ServiceFactory = Callable[..., KoshaKnowledgeService]


def _northwind_with_chain() -> Bundle:
    """Northwind whose gold-members concept carries a supersede chain plus a
    claim rejected against the current head — the fixture the chain/contest
    tests below reconstruct lineage over."""
    bundle = load_bundle(NORTHWIND)
    root = Claim(
        claim_id="root",
        statement="Gold members have 30 days to return an item.",
        source_id="wiki",
        asserted_at=datetime(2026, 1, 1, tzinfo=UTC),
        status=ClaimStatus.SUPERSEDED,
        reviewer="Ann",
    )
    head = Claim(
        claim_id="head",
        statement="Gold members have 45 days to return an item.",
        source_id="returns-policy-2026",
        asserted_at=datetime(2026, 6, 20, tzinfo=UTC),
        status=ClaimStatus.CURRENT,
        supersedes="root",
        reviewer="Ben",
    )
    loser = Claim(
        claim_id="loser",
        statement="Gold members have 20 days to return an item.",
        source_id="unranked-forum",
        asserted_at=datetime(2026, 6, 21, tzinfo=UTC),
        status=ClaimStatus.CONTRADICTED,
        contradicts="head",
        reviewer="Cara",
    )
    concept = bundle.concepts[GOLD]
    bundle.concepts[GOLD] = concept.model_copy(update={"claims": [root, head, loser]})
    return bundle


def test_claim_history_hydrates_a_freshly_loaded_bundle(
    service: KoshaKnowledgeService,
) -> None:
    # The northwind fixture carries no tracked claims; claim_history must not be
    # trivially empty for a served, freshly-loaded bundle.
    view = service.claim_history("policies/shipping")
    assert view["concept_id"] == "policies/shipping"
    assert view["claim_id"] is None
    assert view["entries"]
    assert view["contested_by"] == []


def test_claim_history_unknown_concept_raises(service: KoshaKnowledgeService) -> None:
    with pytest.raises(ConceptNotFoundError):
        service.claim_history("policies/nonexistent")


def test_claim_history_full_concept_view_is_chronological(
    build_service: ServiceFactory,
) -> None:
    service = build_service(_northwind_with_chain())
    view = service.claim_history(GOLD)
    assert [entry["claim_id"] for entry in view["entries"]] == ["root", "head", "loser"]


def test_claim_history_chain_reports_who_superseded_when_from_where_and_by_whom(
    build_service: ServiceFactory,
) -> None:
    service = build_service(_northwind_with_chain())
    view = service.claim_history(GOLD, "root")
    assert [entry["claim_id"] for entry in view["entries"]] == ["root", "head"]
    successor = view["entries"][1]
    assert successor["supersedes"] == "root"
    assert successor["source_id"] == "returns-policy-2026"
    assert successor["reviewer"] == "Ben"
    assert successor["asserted_at"].startswith("2026-06-20")


def test_claim_history_reports_what_contested_a_claim(
    build_service: ServiceFactory,
) -> None:
    service = build_service(_northwind_with_chain())
    view = service.claim_history(GOLD, "head")
    assert len(view["contested_by"]) == 1
    contestant = view["contested_by"][0]
    assert contestant["claim_id"] == "loser"
    assert contestant["status"] == "contradicted"
    assert contestant["contradicts"] == "head"
    assert contestant["reviewer"] == "Cara"


def test_claim_history_unknown_claim_id_raises(build_service: ServiceFactory) -> None:
    service = build_service(_northwind_with_chain())
    with pytest.raises(KeyError):
        service.claim_history(GOLD, "no-such-claim")


def test_claim_history_is_deterministic(build_service: ServiceFactory) -> None:
    service = build_service(_northwind_with_chain())
    assert service.claim_history(GOLD) == service.claim_history(GOLD)
    assert service.claim_history(GOLD, "root") == service.claim_history(GOLD, "root")
