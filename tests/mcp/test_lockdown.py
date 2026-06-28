"""Tool-surface lockdown: the exposed tools are exactly the traversal set.

This is the consumer-enforcement guarantee (system_design §1, §7.1): the only way
an agent can read the bundle is by traversal, so it cannot fall back to grep. The
proof is the tool inventory — no raw-text search tool is registered.
"""

from __future__ import annotations

import asyncio

from kosha.mcp.server import build_server
from kosha.mcp.service import KoshaKnowledgeService

TRAVERSAL_TOOLS = {
    "find_concepts",
    "list_index",
    "read_frontmatter",
    "load_concept",
    "follow_links",
}


def _exposed_tool_names(service: KoshaKnowledgeService) -> set[str]:
    tools = asyncio.run(build_server(service).list_tools())
    return {tool.name for tool in tools}


def test_only_traversal_tools_are_exposed(service: KoshaKnowledgeService) -> None:
    assert _exposed_tool_names(service) == TRAVERSAL_TOOLS


def test_no_raw_search_tool_is_exposed(service: KoshaKnowledgeService) -> None:
    names = _exposed_tool_names(service)
    forbidden = {
        "search",
        "grep",
        "ripgrep",
        "read",
        "read_file",
        "cat",
        "query",
        "dump",
        "load_corpus",
        "list_files",
    }
    assert not names & forbidden
    # Nothing escapes the traversal allowlist.
    assert names <= TRAVERSAL_TOOLS
