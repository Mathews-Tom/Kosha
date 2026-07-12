"""Every traversal tool is explicit read-only/non-destructive/idempotent/closed-world (M9).

Locks the exact ``ToolAnnotations`` protocol contract for both server modes
(legacy single-service and multi-bundle registry, including ``list_bundles``)
so a future tool addition that forgets annotations fails a test, not just a
review.
"""

from __future__ import annotations

import asyncio

from mcp.server.fastmcp import FastMCP

from kosha.mcp.server import build_server
from kosha.mcp.service import KoshaKnowledgeService
from kosha.server.registry import BundleRegistration, BundleRegistry

_EXPECTED = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}


def _annotations_by_name(server: FastMCP) -> dict[str, dict[str, object] | None]:
    async def run() -> dict[str, dict[str, object] | None]:
        tools = await server.list_tools()
        result: dict[str, dict[str, object] | None] = {}
        for tool in tools:
            result[tool.name] = (
                tool.annotations.model_dump() if tool.annotations is not None else None
            )
        return result

    return asyncio.run(run())


def test_single_service_server_annotates_every_tool(
    service: KoshaKnowledgeService,
) -> None:
    server = build_server(service)
    annotations = _annotations_by_name(server)
    assert set(annotations) == {
        "list_index",
        "read_frontmatter",
        "load_concept",
        "find_concepts",
        "follow_links",
        "claim_history",
    }
    for name, fields in annotations.items():
        assert fields is not None, f"{name} has no annotations"
        for key, expected in _EXPECTED.items():
            assert fields[key] == expected, f"{name}.{key}"


def test_registry_server_annotates_every_tool_including_list_bundles(
    service: KoshaKnowledgeService,
) -> None:
    registry = BundleRegistry([BundleRegistration("b", service)])
    server = build_server(registry)
    annotations = _annotations_by_name(server)
    assert set(annotations) == {
        "list_bundles",
        "list_index",
        "read_frontmatter",
        "load_concept",
        "find_concepts",
        "follow_links",
        "claim_history",
    }
    for name, fields in annotations.items():
        assert fields is not None, f"{name} has no annotations"
        for key, expected in _EXPECTED.items():
            assert fields[key] == expected, f"{name}.{key}"
