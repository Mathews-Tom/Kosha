"""MCP protocol surface over a multi-bundle registry (M9 PR-2).

``build_server`` grows a second mode: given a ``BundleRegistry`` instead of a
single service, every traversal tool gains a mandatory ``bundle_id``
parameter. These tests exercise that surface over a real in-memory MCP
client/server session (mirroring tests/mcp/test_acl.py's protocol-level
style) rather than calling the registry directly, so they defend what an
actual MCP client experiences: a tool call with no ``bundle_id`` fails, a
bundle without clearance is denied, and a jump never crosses bundles.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import pytest
from mcp.shared.memory import create_connected_server_and_client_session as connect

from kosha.mcp.server import build_server
from kosha.mcp.service import KoshaKnowledgeService
from kosha.model import Bundle
from kosha.server.registry import BundleRegistration, BundleRegistry

ServiceFactory = Callable[..., KoshaKnowledgeService]


@pytest.fixture
def registry(
    build_service: ServiceFactory, northwind: Bundle, good_bundle: Bundle
) -> BundleRegistry:
    return BundleRegistry(
        [
            BundleRegistration("northwind", build_service(northwind)),
            BundleRegistration("good", build_service(good_bundle)),
            BundleRegistration(
                "locked", build_service(northwind, bundle_access="confidential")
            ),
        ]
    )


def _call(registry: BundleRegistry, name: str, arguments: dict[str, Any]) -> Any:
    server = build_server(registry)

    async def run() -> Any:
        async with connect(server) as client:
            return await client.call_tool(name, arguments)

    return asyncio.run(run())


@pytest.mark.parametrize(
    "tool,args",
    [
        ("list_index", {}),
        ("read_frontmatter", {"concept_id": "policies/shipping"}),
        ("load_concept", {"concept_id": "policies/shipping"}),
        ("find_concepts", {"query": "returns"}),
        ("follow_links", {"concept_id": "policies/shipping"}),
        ("claim_history", {"concept_id": "policies/shipping"}),
    ],
)
def test_every_traversal_tool_requires_bundle_id(
    registry: BundleRegistry, tool: str, args: dict[str, Any]
) -> None:
    # bundle_id is deliberately omitted from every call.
    result = _call(registry, tool, args)
    assert result.isError is True


def test_find_concepts_answers_once_bundle_id_is_supplied(registry: BundleRegistry) -> None:
    result = _call(
        registry, "find_concepts", {"bundle_id": "northwind", "query": "returns", "k": 3}
    )
    assert result.isError is False
    assert result.structuredContent["candidates"]


def test_a_bundle_without_clearance_is_denied_over_mcp(registry: BundleRegistry) -> None:
    result = _call(registry, "list_index", {"bundle_id": "locked"})
    assert result.isError is True


def test_an_unknown_bundle_id_fails_over_mcp(registry: BundleRegistry) -> None:
    result = _call(registry, "list_index", {"bundle_id": "does-not-exist"})
    assert result.isError is True


def test_list_bundles_excludes_a_bundle_without_clearance(registry: BundleRegistry) -> None:
    result = _call(registry, "list_bundles", {})
    assert result.isError is False
    bundle_ids = {entry["bundle_id"] for entry in result.structuredContent["bundles"]}
    assert bundle_ids == {"northwind", "good"}


def test_find_concepts_never_returns_another_bundles_concepts(
    registry: BundleRegistry, good_bundle: Bundle
) -> None:
    result = _call(
        registry,
        "find_concepts",
        {"bundle_id": "good", "query": "customer lifetime value", "k": 5},
    )
    ids = {candidate["concept_id"] for candidate in result.structuredContent["candidates"]}
    assert ids  # the good bundle's own concept was found
    assert ids <= set(good_bundle.concepts)  # never a northwind concept id
