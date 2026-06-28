"""End-to-end: an MCP client answers a Northwind query by hybrid traversal.

The success contract for M11: a client answers via
find_concepts -> read_frontmatter -> load_concept -> follow_links, loading only the
relevant concept set (never the whole corpus), and load_concept hides expired
claims (system_design §4.4, §3.2).
"""

from __future__ import annotations

import asyncio
from typing import Any

from mcp.shared.memory import create_connected_server_and_client_session as connect

from kosha.mcp.server import build_server
from kosha.mcp.service import KoshaKnowledgeService

_TARGET = "policies/returns/gold-members"
_QUERY = "how long does a gold member have to return an item"
_UNRELATED = {"references/glossary", "references/channels", "entities/order"}


def test_gold_member_return_query(temporal_service: KoshaKnowledgeService) -> None:
    server = build_server(temporal_service)
    total = len(temporal_service.bundle.concepts)
    loaded: list[str] = []

    async def answer() -> str:
        async with connect(server) as client:

            async def structured(name: str, args: dict[str, Any]) -> Any:
                result = await client.call_tool(name, args)
                assert not result.isError
                return result.structuredContent

            # 1. Jump: land near the answer (embedding search, no bodies loaded).
            found = await structured("find_concepts", {"query": _QUERY, "k": 3})
            seeds = [candidate["concept_id"] for candidate in found["candidates"]]
            assert _TARGET not in seeds  # the raw jump misses the gold variant

            # 2. Traverse: from a seed, follow links to reach the gold concept.
            via = None
            for seed in seeds:
                await structured("read_frontmatter", {"concept_id": seed})
                links = await structured("follow_links", {"concept_id": seed})
                neighbors = {
                    link["concept_id"]
                    for link in links["out_links"] + links["backlinks"]
                }
                if _TARGET in neighbors:
                    via = seed
                    break
            assert via is not None
            await structured("load_concept", {"concept_id": via})
            loaded.append(via)

            # 3. Peek then load only the answer concept.
            front = await structured("read_frontmatter", {"concept_id": _TARGET})
            assert front["type"] == "Policy"
            concept = await structured("load_concept", {"concept_id": _TARGET})
            loaded.append(_TARGET)
            return concept["body"]

    body = asyncio.run(answer())

    # The answer is present and the expired claim is hidden by the temporal filter.
    assert "45 days" in body
    assert "60 days" not in body
    assert "2025 pilot" not in body

    # Only the relevant set was loaded — never the whole corpus.
    assert _TARGET in loaded
    assert len(set(loaded)) <= 3
    assert len(set(loaded)) < total
    assert not set(loaded) & _UNRELATED
