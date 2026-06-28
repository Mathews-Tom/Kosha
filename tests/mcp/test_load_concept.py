"""load_concept: temporal claim filtering and the bundle-level access gate."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from kosha.mcp.service import AccessDeniedError, KoshaKnowledgeService
from kosha.model import Bundle


def test_load_concept_hides_expired_claim(
    temporal_service: KoshaKnowledgeService,
) -> None:
    view = temporal_service.load_concept("policies/returns/gold-members")
    assert "45 days" in view["body"]
    assert "60 days" not in view["body"]
    assert "2025 pilot" not in view["body"]
    assert view["asof"] is None


def test_load_concept_asof_reveals_historical_claim(
    temporal_service: KoshaKnowledgeService,
) -> None:
    view = temporal_service.load_concept(
        "policies/returns/gold-members", asof="2025-06-01T00:00:00+00:00"
    )
    assert "60 days" in view["body"]
    assert "45 days" not in view["body"]


def test_load_concept_returns_plain_body_verbatim(
    service: KoshaKnowledgeService,
) -> None:
    view = service.load_concept("policies/shipping")
    expected = service.bundle.concepts["policies/shipping"]
    assert view["body"] == expected.body
    assert view["out_links"] == list(expected.out_links)


def test_load_concept_denies_uncleared_bundle(
    northwind: Bundle,
    build_service: Callable[..., KoshaKnowledgeService],
) -> None:
    locked = build_service(northwind, bundle_access="confidential")
    with pytest.raises(AccessDeniedError):
        locked.load_concept("policies/shipping")


def test_load_concept_allows_cleared_bundle(
    northwind: Bundle,
    build_service: Callable[..., KoshaKnowledgeService],
) -> None:
    cleared = build_service(
        northwind, bundle_access="confidential", clearance=["confidential"]
    )
    assert cleared.load_concept("policies/shipping")["body"]
