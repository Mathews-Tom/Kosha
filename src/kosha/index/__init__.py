"""Derived embedding index over a bundle's concepts.

The index is rebuildable from Git at any time and is never the source of truth
(system_design §3): it maps each ``concept_id`` to an embedding of the concept's
description + body and answers nearest-neighbor queries. It is reused downstream by
the dedup resolver (M6) and the MCP ``find_concepts`` jump (M11).
"""

from __future__ import annotations

from kosha.index.embedding import EmbeddingIndex, Neighbor

__all__ = ["EmbeddingIndex", "Neighbor"]
