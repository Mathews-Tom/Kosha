"""Deterministic traversal core behind the MCP consumer surface.

This module is the single source of truth for the bundle-traversal operations the
MCP server exposes (system_design §4.4, §2.2). It has **no dependency on the
``mcp`` SDK**, so the producer loop and the non-MCP fallback can reuse it; the
FastMCP server (:mod:`kosha.mcp.server`) is a thin protocol shell over these
methods.

The service exposes only *traversal* and *jump* operations — never a raw-text
search endpoint — so the served MCP knowledge interface is traversal-first
(system_design §1, §7.1). Retrieval is the hybrid path: an embedding *jump*
(:meth:`find_concepts`) lands near the answer, then structured *traversal*
(:meth:`list_index`, :meth:`read_frontmatter`, :meth:`load_concept`,
:meth:`follow_links`) expands and verifies, loading only the relevant concept set.

Every result is a plain JSON-serializable mapping so the same payload flows
unchanged through the MCP protocol and the fallback path.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import TypedDict

from kosha.contradiction import effective_claims
from kosha.index.embedding import EmbeddingIndex
from kosha.indexlog.index import regenerate_index
from kosha.merge.claims import render_claim_set
from kosha.merge.lineage import ClaimLineageEntry, claim_chain, concept_history, contested_by
from kosha.model import Bundle, Concept
from kosha.pipeline.writer import hydrate_claims


def resolve_clearance(env: Mapping[str, str]) -> frozenset[str]:
    """Parse the caller's clearance labels from ``KOSHA_CLEARANCE`` (comma-separated)."""
    raw = env.get("KOSHA_CLEARANCE", "")
    return frozenset(item.strip() for item in raw.split(",") if item.strip())


def resolve_bundle_access(env: Mapping[str, str]) -> str | None:
    """Parse the bundle's required access label from ``KOSHA_BUNDLE_ACCESS``."""
    return env.get("KOSHA_BUNDLE_ACCESS", "").strip() or None


class IndexEntryView(TypedDict):
    """One linked item in a :meth:`KoshaKnowledgeService.list_index` listing."""

    title: str
    target: str
    description: str | None


class IndexSectionView(TypedDict):
    """A headed group of entries in an index listing."""

    heading: str
    entries: list[IndexEntryView]


class IndexView(TypedDict):
    """The structured directory listing returned by ``list_index``."""

    scope: str
    sections: list[IndexSectionView]


class FrontmatterView(TypedDict):
    """The frontmatter peek returned by ``read_frontmatter`` (no body)."""

    concept_id: str
    type: str
    title: str | None
    description: str | None
    tags: list[str]
    timestamp: str | None
    effective_from: str | None
    effective_to: str | None
    access_level: str | None


class ConceptView(TypedDict):
    """The body returned by ``load_concept``, filtered to in-force claims."""

    concept_id: str
    type: str
    title: str | None
    body: str
    out_links: list[str]
    asof: str | None


class CandidateView(TypedDict):
    """One ranked candidate from the ``find_concepts`` embedding jump."""

    concept_id: str
    score: float
    description: str | None


class FindView(TypedDict):
    """The ranked jump result returned by ``find_concepts``."""

    query: str
    candidates: list[CandidateView]


class LinkView(TypedDict):
    """One edge in a ``follow_links`` result; ``present`` is False if dangling."""

    concept_id: str
    description: str | None
    present: bool


class LinksView(TypedDict):
    """The neighborhood returned by ``follow_links``: out-links and backlinks."""

    concept_id: str
    out_links: list[LinkView]
    backlinks: list[LinkView]


class ClaimLineageEntryView(TypedDict):
    """One claim's provenance, as returned by ``claim_history``."""

    claim_id: str
    statement: str
    status: str
    source_id: str
    asserted_at: str
    reviewer: str | None
    supersedes: str | None
    contradicts: str | None
    citations: list[str]
    effective_from: str | None
    effective_to: str | None


class ClaimHistoryView(TypedDict):
    """The lineage returned by ``claim_history``.

    ``entries`` is the whole concept's claim history (``claim_id=None``) or the
    single supersede chain ``claim_id`` belongs to; ``contested_by`` lists the
    claims rejected specifically against ``claim_id`` (empty when unscoped).
    """

    concept_id: str
    claim_id: str | None
    entries: list[ClaimLineageEntryView]
    contested_by: list[ClaimLineageEntryView]


class ConceptNotFoundError(KeyError):
    """Raised when a requested ``concept_id`` is not in the bundle."""


class AccessDeniedError(PermissionError):
    """Raised when the caller's clearance does not cover the bundle's access level."""


class KoshaKnowledgeService:
    """Traversal-only knowledge service over a loaded :class:`Bundle`.

    Construct it with the bundle and its M4 embedding index; the MCP server and the
    fallback both delegate here. The index is held for the embedding *jump*
    (:meth:`find_concepts`); the structural traversal methods read only the bundle.

    Access is the **bundle-level** permission unit (system_design §6, §7.2): when
    ``bundle_access`` is set, a caller is served only if ``bundle_access`` is in its
    ``clearance``. There is no concept-level ACL — the bundle is granted or denied
    as a whole.
    """

    def __init__(
        self,
        bundle: Bundle,
        index: EmbeddingIndex,
        *,
        bundle_access: str | None = None,
        clearance: Iterable[str] = (),
    ) -> None:
        self._bundle = bundle
        self._index = index
        self._bundle_access = bundle_access
        self._clearance = frozenset(clearance)

    @property
    def bundle(self) -> Bundle:
        return self._bundle

    def list_index(self, scope: str = "") -> IndexView:
        """Return the structured listing of a directory's direct contents.

        ``scope`` is a bundle directory (``""`` is the root); the listing names
        immediate subdirectories (each linking its own ``index.md``) and the
        directory's concept documents with their descriptions — the progressive-
        disclosure map an agent reads before opening any document.
        """
        self._require_access()
        doc = regenerate_index(self._bundle, scope)
        sections: list[IndexSectionView] = [
            {
                "heading": section.heading,
                "entries": [
                    {
                        "title": entry.title,
                        "target": entry.target,
                        "description": entry.description,
                    }
                    for entry in section.entries
                ],
            }
            for section in doc.sections
        ]
        return {"scope": scope, "sections": sections}

    def read_frontmatter(self, concept_id: str) -> FrontmatterView:
        """Return a concept's frontmatter without loading its body.

        The cheap peek between the embedding jump and a full
        :meth:`load_concept`: an agent reads ``type``/``description``/effective
        dates to decide whether a candidate is worth loading.
        """
        self._require_access()
        concept = self._require_concept(concept_id)
        fm = concept.frontmatter
        return {
            "concept_id": concept_id,
            "type": fm.type,
            "title": fm.title,
            "description": fm.description,
            "tags": list(fm.tags),
            "timestamp": _iso(fm.timestamp),
            "effective_from": _iso(fm.effective_from),
            "effective_to": _iso(fm.effective_to),
            "access_level": fm.access_level,
        }

    def load_concept(self, concept_id: str, *, asof: str | None = None) -> ConceptView:
        """Load a concept's body, filtered to the claims in force at ``asof``.

        The access-gated, temporally-filtered read (system_design §4.4, §3.2). The
        bundle-level access gate runs first, so an uncleared bundle yields nothing.
        By default (``asof=None``) only currently-in-force claims render — an
        expired claim (one whose ``effective_to`` has passed) is hidden; pass an ISO
        ``asof`` for the historical view valid at that instant. A concept whose body
        is a plain document (no tracked claims) is returned verbatim.
        """
        self._require_access()
        concept = self._require_concept(concept_id)
        moment = _parse_asof(asof)
        if concept.claims:
            body = render_claim_set(effective_claims(concept.claims, asof=moment))
        else:
            body = concept.body
        return {
            "concept_id": concept_id,
            "type": concept.frontmatter.type,
            "title": concept.frontmatter.title,
            "body": body,
            "out_links": list(concept.out_links),
            "asof": _iso(moment),
        }

    def find_concepts(self, query: str, k: int = 3) -> FindView:
        """Jump to the ``k`` concepts nearest ``query`` in the embedding space.

        The latency mechanism of the hybrid path (system_design §4.4): one
        embedding round-trip lands near the answer, returning ranked
        ``concept_id``s with their descriptions — not bodies — so the agent then
        traverses (read_frontmatter, load_concept, follow_links) to expand and
        verify. This is a *jump*, never a raw-text search of the corpus.
        """
        self._require_access()
        candidates: list[CandidateView] = []
        for neighbor in self._index.query_text(query, k):
            concept = self._bundle.concepts.get(neighbor.concept_id)
            description = concept.frontmatter.description if concept else None
            candidates.append(
                {
                    "concept_id": neighbor.concept_id,
                    "score": neighbor.score,
                    "description": description,
                }
            )
        return {"query": query, "candidates": candidates}

    def follow_links(self, concept_id: str) -> LinksView:
        """Return a concept's neighborhood: its out-links and its backlinks.

        Traversal expansion (system_design §4.4): out-links are the concept's
        bundle-relative edges (each flagged ``present`` or intentionally dangling);
        backlinks are the reverse edges ("cited by"). Both carry descriptions so the
        agent can decide what to load next without loading anything.
        """
        self._require_access()
        concept = self._require_concept(concept_id)
        out_links = [self._link_view(target) for target in concept.out_links]
        backlinks = [
            self._link_view(other_id)
            for other_id in sorted(self._bundle.concepts)
            if concept_id in self._bundle.concepts[other_id].out_links
        ]
        return {
            "concept_id": concept_id,
            "out_links": out_links,
            "backlinks": backlinks,
        }

    def claim_history(self, concept_id: str, claim_id: str | None = None) -> ClaimHistoryView:
        """Return a concept's claim lineage: full audit trail, or one claim's chain.

        Pass no ``claim_id`` for the whole concept's claim history — current,
        superseded, and contradicted claims alike, chronological — the browsing
        view. Pass a specific ``claim_id`` to get just that claim's supersede
        chain (oldest to newest) plus the claims rejected against it, answering
        "what superseded this claim, when, from which source, and under which
        approver identity." Raises :class:`KeyError` when ``claim_id`` is given
        but not present on the concept.

        A concept loaded fresh from disk carries no tracked claims; this
        hydrates them from the body first (one current claim per paragraph, no
        prior history to reconstruct) so the tool is never trivially empty for a
        served bundle — the same fallback :meth:`load_concept` relies on for its
        temporal filter.
        """
        self._require_access()
        concept = hydrate_claims(self._require_concept(concept_id), asserted_at=datetime.now(UTC))
        claims = concept.claims
        contested: list[ClaimLineageEntry] = []
        if claim_id is None:
            entries = concept_history(claims)
        else:
            entries = claim_chain(claims, claim_id)
            contested = contested_by(claims, claim_id)
        return {
            "concept_id": concept_id,
            "claim_id": claim_id,
            "entries": [_claim_view(entry) for entry in entries],
            "contested_by": [_claim_view(entry) for entry in contested],
        }

    def _link_view(self, target_id: str) -> LinkView:
        target = self._bundle.concepts.get(target_id)
        return {
            "concept_id": target_id,
            "description": target.frontmatter.description if target else None,
            "present": target is not None,
        }

    def _require_access(self) -> None:
        if self._bundle_access is not None and self._bundle_access not in self._clearance:
            raise AccessDeniedError(
                f"bundle access level {self._bundle_access!r} not in clearance"
            )

    def _require_concept(self, concept_id: str) -> Concept:
        concept = self._bundle.concepts.get(concept_id)
        if concept is None:
            raise ConceptNotFoundError(concept_id)
        return concept


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _parse_asof(value: str | None) -> datetime | None:
    if value is None:
        return None
    moment = datetime.fromisoformat(value)
    if moment.tzinfo is None:
        raise ValueError(
            f"asof {value!r} must be timezone-aware (e.g. 2025-06-01T00:00:00+00:00)"
        )
    return moment


def _claim_view(entry: ClaimLineageEntry) -> ClaimLineageEntryView:
    return {
        "claim_id": entry.claim_id,
        "statement": entry.statement,
        "status": entry.status.value,
        "source_id": entry.source_id,
        "asserted_at": entry.asserted_at.isoformat(),
        "reviewer": entry.reviewer,
        "supersedes": entry.supersedes,
        "contradicts": entry.contradicts,
        "citations": list(entry.citations),
        "effective_from": _iso(entry.effective_from),
        "effective_to": _iso(entry.effective_to),
    }
