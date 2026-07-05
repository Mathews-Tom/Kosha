"""Shared fixtures for the MCP consumer-surface tests."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from kosha.index.embedding import EmbeddingIndex
from kosha.mcp.service import KoshaKnowledgeService
from kosha.model import Bundle, Claim
from kosha.okf.load import load_bundle
from kosha.providers import LexicalEmbeddingProvider

NORTHWIND = Path(__file__).resolve().parents[2] / "bundles" / "northwind"
GOLD = "policies/returns/gold-members"
GOOD_BUNDLE = Path(__file__).resolve().parents[1] / "fixtures" / "good_bundle"


def make_service(
    bundle: Bundle,
    *,
    bundle_access: str | None = None,
    clearance: Iterable[str] = (),
) -> KoshaKnowledgeService:
    """Build a service over ``bundle`` with the deterministic local embedder."""
    index = EmbeddingIndex.build(bundle, LexicalEmbeddingProvider())
    return KoshaKnowledgeService(
        bundle, index, bundle_access=bundle_access, clearance=clearance
    )


def northwind_with_temporal_claims() -> Bundle:
    """Northwind whose gold-members concept carries a current + an expired claim.

    The on-disk corpus has no tracked claims, so this is how the tests exercise the
    temporal filter: a 45-day claim in force from 2026, and a 60-day "2025 pilot"
    claim whose validity window has closed (``effective_to`` in the past).
    """
    bundle = load_bundle(NORTHWIND)
    concept = bundle.concepts[GOLD]
    current = Claim(
        claim_id="gold-current",
        statement="A Gold member has 45 days from delivery to return an item.",
        source_id="returns-policy-2026",
        asserted_at=datetime(2026, 6, 20, tzinfo=UTC),
        effective_from=datetime(2026, 6, 20, tzinfo=UTC),
        citations=["/policies/returns/standard.md"],
    )
    expired = Claim(
        claim_id="gold-pilot",
        statement="During the 2025 pilot a Gold member had 60 days to return an item.",
        source_id="returns-pilot-2025",
        asserted_at=datetime(2025, 1, 1, tzinfo=UTC),
        effective_from=datetime(2025, 1, 1, tzinfo=UTC),
        effective_to=datetime(2026, 1, 1, tzinfo=UTC),
        citations=["/policies/returns/standard.md"],
    )
    bundle.concepts[GOLD] = concept.model_copy(update={"claims": [current, expired]})
    return bundle


@pytest.fixture
def northwind() -> Bundle:
    return load_bundle(NORTHWIND)


@pytest.fixture
def good_bundle() -> Bundle:
    return load_bundle(GOOD_BUNDLE)


@pytest.fixture
def service(northwind: Bundle) -> KoshaKnowledgeService:
    return make_service(northwind)


@pytest.fixture
def temporal_service() -> KoshaKnowledgeService:
    return make_service(northwind_with_temporal_claims())


@pytest.fixture
def build_service() -> Callable[..., KoshaKnowledgeService]:
    return make_service
