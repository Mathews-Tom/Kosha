"""Consumer surface: the traversal-only knowledge service (system_design §4.4, §2.2).

Importing this package never pulls the ``mcp`` SDK — only the deterministic
:class:`KoshaKnowledgeService`, which the producer loop and the non-MCP fallback
reuse. The FastMCP protocol shell lives in :mod:`kosha.mcp.server`, imported
explicitly by the server entrypoint and the MCP tests.
"""

from __future__ import annotations

from kosha.mcp.service import (
    AccessDeniedError,
    CandidateView,
    ConceptNotFoundError,
    ConceptView,
    FindView,
    FrontmatterView,
    IndexView,
    KoshaKnowledgeService,
    LinksView,
    LinkView,
)

__all__ = [
    "AccessDeniedError",
    "CandidateView",
    "ConceptNotFoundError",
    "ConceptView",
    "FindView",
    "FrontmatterView",
    "IndexView",
    "KoshaKnowledgeService",
    "LinkView",
    "LinksView",
]
