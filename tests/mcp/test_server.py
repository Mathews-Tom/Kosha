"""MCP protocol tests: tools register and answer over an in-memory client."""

from __future__ import annotations

import asyncio
from typing import Any

from mcp.shared.memory import create_connected_server_and_client_session as connect

from kosha.mcp.server import build_server
from kosha.mcp.service import KoshaKnowledgeService


def _tool_names(service: KoshaKnowledgeService) -> set[str]:
    server = build_server(service)
    tools = asyncio.run(server.list_tools())
    return {tool.name for tool in tools}


def _call(service: KoshaKnowledgeService, name: str, arguments: dict[str, Any]) -> Any:
    server = build_server(service)

    async def run() -> Any:
        async with connect(server) as client:
            result = await client.call_tool(name, arguments)
            assert not result.isError
            return result.structuredContent

    return asyncio.run(run())


def test_scaffold_exposes_traversal_tools(service: KoshaKnowledgeService) -> None:
    names = _tool_names(service)
    assert {"list_index", "read_frontmatter", "load_concept"} <= names
    # No raw-text search tool leaks in even at the scaffold stage.
    assert not names & {"search", "grep", "read_file", "query", "load_corpus"}


def test_read_frontmatter_over_mcp(service: KoshaKnowledgeService) -> None:
    structured = _call(
        service, "read_frontmatter", {"concept_id": "policies/returns/gold-members"}
    )
    assert structured["type"] == "Policy"
    assert structured["title"] == "Gold Member Returns"


def test_list_index_over_mcp(service: KoshaKnowledgeService) -> None:
    structured = _call(service, "list_index", {"scope": "policies/returns"})
    targets = {
        entry["target"]
        for section in structured["sections"]
        for entry in section["entries"]
    }
    assert "policies/returns/gold-members" in targets


def test_load_concept_over_mcp_hides_expired(
    temporal_service: KoshaKnowledgeService,
) -> None:
    structured = _call(
        temporal_service, "load_concept", {"concept_id": "policies/returns/gold-members"}
    )
    assert "45 days" in structured["body"]
    assert "60 days" not in structured["body"]
