"""FastMCP protocol shell over the traversal-only knowledge service.

A thin adapter (system_design §1 "deterministic spine, isolated surfaces"): it
registers the bundle-traversal operations of :class:`KoshaKnowledgeService` as MCP
tools and delegates straight to them. The exposed MCP tool set is the
traversal/jump surface (system_design §4.4) and deliberately has no raw-text search
tool. Host-level filesystem sandboxing is a separate serving boundary.

Importing this module requires the optional ``mcp`` dependency (``kosha-okf[mcp]``);
the pure service in :mod:`kosha.mcp.service` does not.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from kosha.mcp.service import (
    ConceptView,
    FindView,
    FrontmatterView,
    IndexView,
    KoshaKnowledgeService,
    LinksView,
)

_INSTRUCTIONS = (
    "Answer from this OKF bundle by traversal, never by guessing or grepping. "
    "Jump with find_concepts to land near the answer, read_frontmatter to peek, "
    "load_concept only for the concepts you need, and follow_links to expand. "
    "These traversal tools are the only way to read the knowledge base."
)


def build_server(
    service: KoshaKnowledgeService, *, name: str = "kosha-knowledge"
) -> FastMCP:
    """Build a FastMCP server whose only knowledge tools traverse ``service``.

    Each tool is a one-line delegation to the service so the deterministic
    traversal logic has a single home; the server adds only the MCP protocol.
    """
    server = FastMCP(name, instructions=_INSTRUCTIONS)

    @server.tool()
    def list_index(scope: str = "") -> IndexView:
        """List a bundle directory's direct contents (subdirectories + concepts).

        Pass an empty ``scope`` for the bundle root; descend by passing a
        subdirectory path. This is the progressive-disclosure map — read it before
        opening any concept.
        """
        return service.list_index(scope)

    @server.tool()
    def read_frontmatter(concept_id: str) -> FrontmatterView:
        """Read a concept's frontmatter (type, description, dates) without its body.

        The cheap peek used to decide whether a candidate concept is worth a full
        load_concept.
        """
        return service.read_frontmatter(concept_id)

    @server.tool()
    def load_concept(concept_id: str, asof: str | None = None) -> ConceptView:
        """Load a concept's body, showing only the claims currently in force.

        An expired claim is hidden by default; pass an ISO ``asof`` timestamp to
        read the historical view valid at that instant. Load a concept only after
        read_frontmatter says it is relevant.
        """
        return service.load_concept(concept_id, asof=asof)

    @server.tool()
    def find_concepts(query: str, k: int = 3) -> FindView:
        """Jump to the concepts most relevant to a question (embedding search).

        Returns ranked concept ids with descriptions — not bodies. Start here, then
        read_frontmatter and load_concept the candidates worth reading. This is a
        jump near the answer, not a raw-text search of the corpus.
        """
        return service.find_concepts(query, k)

    @server.tool()
    def follow_links(concept_id: str) -> LinksView:
        """List a concept's links and backlinks so you can traverse the graph.

        Use it to expand from a loaded concept to its related concepts; load only
        the neighbors you actually need.
        """
        return service.follow_links(concept_id)

    return server


def resolve_clearance(env: Mapping[str, str]) -> frozenset[str]:
    """Parse the caller's clearance labels from ``KOSHA_CLEARANCE`` (comma-separated)."""
    raw = env.get("KOSHA_CLEARANCE", "")
    return frozenset(item.strip() for item in raw.split(",") if item.strip())


def resolve_bundle_access(env: Mapping[str, str]) -> str | None:
    """Parse the bundle's required access label from ``KOSHA_BUNDLE_ACCESS``."""
    return env.get("KOSHA_BUNDLE_ACCESS", "").strip() or None


def main() -> None:
    """Run the stdio MCP server over a bundle given by argv or ``KOSHA_BUNDLE``.

    Bundle-level access is opt-in: set ``KOSHA_BUNDLE_ACCESS`` to the label the
    bundle requires and ``KOSHA_CLEARANCE`` to the comma-separated labels the
    served caller holds. Leaving both unset serves the bundle openly, matching
    prior behavior. Setting only ``KOSHA_BUNDLE_ACCESS`` denies every caller
    (clearance defaults to empty) rather than silently serving the bundle open.
    """
    from kosha.index.embedding import EmbeddingIndex
    from kosha.okf.load import load_bundle
    from kosha.providers import resolve_embedding_provider

    arg = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("KOSHA_BUNDLE")
    if not arg:
        raise SystemExit("usage: kosha-mcp <bundle-path>  (or set KOSHA_BUNDLE)")
    bundle = load_bundle(Path(arg))
    index = EmbeddingIndex.build(bundle, resolve_embedding_provider())
    service = KoshaKnowledgeService(
        bundle,
        index,
        bundle_access=resolve_bundle_access(os.environ),
        clearance=resolve_clearance(os.environ),
    )
    build_server(service).run()
