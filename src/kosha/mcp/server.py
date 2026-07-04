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
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from kosha.mcp.service import (
    ClaimHistoryView,
    ConceptView,
    FindView,
    FrontmatterView,
    IndexView,
    KoshaKnowledgeService,
    LinksView,
    resolve_bundle_access,
    resolve_clearance,
)
from kosha.server.registry import BundleRegistration, BundleRegistry

_INSTRUCTIONS = (
    "Answer from this OKF bundle by traversal, never by guessing or grepping. "
    "Jump with find_concepts to land near the answer, read_frontmatter to peek, "
    "load_concept only for the concepts you need, and follow_links to expand. "
    "These traversal tools are the only way to read the knowledge base."
)


def build_server(
    registry: BundleRegistry | KoshaKnowledgeService, *, name: str = "kosha-knowledge"
) -> FastMCP:
    """Build a FastMCP server over a single service or explicit-bundle registry."""
    if isinstance(registry, KoshaKnowledgeService):
        return _build_single_service_server(registry, name=name)
    return _build_registry_server(registry, name=name)


def _build_registry_server(registry: BundleRegistry, *, name: str) -> FastMCP:
    """Build a FastMCP server whose tools require an explicit ``bundle_id``."""
    server = FastMCP(name, instructions=_INSTRUCTIONS)

    @server.tool()
    def list_bundles() -> dict[str, list[str]]:
        """List bundle ids visible to the caller's configured clearance."""
        return {"bundles": registry.authorized_bundle_ids()}

    @server.tool()
    def list_index(bundle_id: str, scope: str = "") -> IndexView:
        """List a bundle directory's direct contents (subdirectories + concepts)."""
        return registry.require_service(bundle_id).list_index(scope)

    @server.tool()
    def read_frontmatter(bundle_id: str, concept_id: str) -> FrontmatterView:
        """Read a concept's frontmatter without its body."""
        return registry.require_service(bundle_id).read_frontmatter(concept_id)

    @server.tool()
    def load_concept(
        bundle_id: str, concept_id: str, asof: str | None = None
    ) -> ConceptView:
        """Load a concept's body, showing only the claims currently in force."""
        return registry.require_service(bundle_id).load_concept(concept_id, asof=asof)

    @server.tool()
    def find_concepts(bundle_id: str, query: str, k: int = 3) -> FindView:
        """Jump to concepts within one addressed bundle, never across bundles."""
        return registry.require_service(bundle_id).find_concepts(query, k)

    @server.tool()
    def follow_links(bundle_id: str, concept_id: str) -> LinksView:
        """List a concept's links and backlinks so you can traverse the graph."""
        return registry.require_service(bundle_id).follow_links(concept_id)

    @server.tool()
    def claim_history(
        bundle_id: str, concept_id: str, claim_id: str | None = None
    ) -> ClaimHistoryView:
        """Show a concept's claim lineage: full audit trail, or one claim's chain."""
        return registry.require_service(bundle_id).claim_history(concept_id, claim_id)

    return server


def _build_single_service_server(
    service: KoshaKnowledgeService, *, name: str
) -> FastMCP:
    """Build the legacy single-bundle in-process server used by existing tests."""
    server = FastMCP(name, instructions=_INSTRUCTIONS)

    @server.tool()
    def list_index(scope: str = "") -> IndexView:
        """List a bundle directory's direct contents (subdirectories + concepts)."""
        return service.list_index(scope)

    @server.tool()
    def read_frontmatter(concept_id: str) -> FrontmatterView:
        """Read a concept's frontmatter without its body."""
        return service.read_frontmatter(concept_id)

    @server.tool()
    def load_concept(concept_id: str, asof: str | None = None) -> ConceptView:
        """Load a concept's body, showing only the claims currently in force."""
        return service.load_concept(concept_id, asof=asof)

    @server.tool()
    def find_concepts(query: str, k: int = 3) -> FindView:
        """Jump to concepts within this bundle, never raw-searching the corpus."""
        return service.find_concepts(query, k)

    @server.tool()
    def follow_links(concept_id: str) -> LinksView:
        """List a concept's links and backlinks so you can traverse the graph."""
        return service.follow_links(concept_id)

    @server.tool()
    def claim_history(concept_id: str, claim_id: str | None = None) -> ClaimHistoryView:
        """Show a concept's claim lineage: full audit trail, or one claim's chain."""
        return service.claim_history(concept_id, claim_id)

    return server


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
    build_server(BundleRegistry([BundleRegistration(bundle_id="default", service=service)])).run()
