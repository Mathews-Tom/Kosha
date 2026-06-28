"""Deterministic traversal core behind the MCP consumer surface.

This module is the single source of truth for the bundle-traversal operations the
MCP server exposes (system_design §4.4, §2.2). It has **no dependency on the
``mcp`` SDK**, so the producer loop and the non-MCP fallback can reuse it; the
FastMCP server (:mod:`kosha.mcp.server`) is a thin protocol shell over these
methods.

The service exposes only *traversal* and *jump* operations — never a raw-text
search — so a connected agent cannot grep the corpus (system_design §1 "consumer
cannot silently degrade", §7.1). Retrieval is the hybrid path: an embedding *jump*
(:meth:`find_concepts`) lands near the answer, then structured *traversal*
(:meth:`list_index`, :meth:`read_frontmatter`, :meth:`load_concept`,
:meth:`follow_links`) expands and verifies, loading only the relevant concept set.

Every result is a plain JSON-serializable mapping so the same payload flows
unchanged through the MCP protocol and the fallback path.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import TypedDict

from kosha.contradiction import effective_claims
from kosha.index.embedding import EmbeddingIndex
from kosha.indexlog.index import regenerate_index
from kosha.merge.claims import render_claim_set
from kosha.model import Bundle, Concept


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
    return datetime.fromisoformat(value) if value is not None else None
