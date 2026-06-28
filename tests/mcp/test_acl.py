"""Bundle-level ACL: the whole bundle is the permission unit (system_design §6, §7.2)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import pytest
from mcp.shared.memory import create_connected_server_and_client_session as connect

from kosha.mcp.server import build_server
from kosha.mcp.service import AccessDeniedError, KoshaKnowledgeService
from kosha.model import Bundle

ServiceFactory = Callable[..., KoshaKnowledgeService]


def test_every_tool_denies_an_uncleared_bundle(
    northwind: Bundle, build_service: ServiceFactory
) -> None:
    locked = build_service(northwind, bundle_access="confidential")
    with pytest.raises(AccessDeniedError):
        locked.list_index()
    with pytest.raises(AccessDeniedError):
        locked.read_frontmatter("policies/shipping")
    with pytest.raises(AccessDeniedError):
        locked.load_concept("policies/shipping")
    with pytest.raises(AccessDeniedError):
        locked.find_concepts("returns")
    with pytest.raises(AccessDeniedError):
        locked.follow_links("policies/shipping")


def test_clearance_unlocks_every_tool(
    northwind: Bundle, build_service: ServiceFactory
) -> None:
    cleared = build_service(
        northwind, bundle_access="confidential", clearance=["confidential"]
    )
    assert cleared.list_index()["sections"]
    assert cleared.read_frontmatter("policies/shipping")["type"]
    assert cleared.load_concept("policies/shipping")["body"]
    assert cleared.find_concepts("returns")["candidates"]
    assert "out_links" in cleared.follow_links("policies/shipping")


def test_public_bundle_needs_no_clearance(service: KoshaKnowledgeService) -> None:
    # Default bundle_access is None: an unrestricted bundle is open to any caller.
    assert service.list_index()["sections"]


def test_access_denied_surfaces_as_a_tool_error_over_mcp(
    northwind: Bundle, build_service: ServiceFactory
) -> None:
    locked = build_service(northwind, bundle_access="confidential")
    server = build_server(locked)

    async def run() -> bool:
        async with connect(server) as client:
            result = await client.call_tool(
                "load_concept", {"concept_id": "policies/shipping"}
            )
            return result.isError

    assert asyncio.run(run()) is True
