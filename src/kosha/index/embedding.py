"""Concept embedding index with cosine nearest-neighbor lookup.

Built from a :class:`~kosha.model.Bundle` and an
:class:`~kosha.providers.base.EmbeddingProvider`, the index embeds each concept's
*description + body* and answers ``query``/``query_text`` with the top-k nearest
concepts by cosine similarity. It is derived, rebuildable state and can be
persisted to (and reloaded from) a local JSON file.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from kosha.model import Bundle, Concept
from kosha.providers.base import EmbeddingProvider, Vector


@dataclass(frozen=True)
class Neighbor:
    """A concept ranked by similarity to a query."""

    concept_id: str
    score: float


def index_text(concept: Concept) -> str:
    """Return the text indexed for a concept: its description then its body."""
    description = concept.frontmatter.description or ""
    return f"{description}\n{concept.body}".strip()


class EmbeddingIndex:
    """An in-memory cosine nearest-neighbor index over concept embeddings."""

    def __init__(
        self,
        provider: EmbeddingProvider,
        entries: dict[str, Vector],
    ) -> None:
        self._provider = provider
        self._entries = entries
        self._norms = {cid: _norm(vec) for cid, vec in entries.items()}

    @classmethod
    def build(cls, bundle: Bundle, provider: EmbeddingProvider) -> EmbeddingIndex:
        """Embed every concept in ``bundle`` (sorted for determinism)."""
        concept_ids = sorted(bundle.concepts)
        texts = [index_text(bundle.concepts[cid]) for cid in concept_ids]
        vectors = provider.embed(texts) if texts else []
        return cls(provider, dict(zip(concept_ids, vectors, strict=True)))

    @property
    def provider(self) -> EmbeddingProvider:
        return self._provider

    @property
    def concept_ids(self) -> list[str]:
        return list(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def query(self, vector: Vector, k: int = 5) -> list[Neighbor]:
        """Return the ``k`` concepts most similar to ``vector`` (descending)."""
        if k <= 0:
            raise ValueError("k must be positive")
        query_norm = _norm(vector)
        neighbors = [
            Neighbor(cid, _cosine(vector, query_norm, vec, self._norms[cid]))
            for cid, vec in self._entries.items()
        ]
        neighbors.sort(key=lambda n: (-n.score, n.concept_id))
        return neighbors[:k]

    def query_text(self, text: str, k: int = 5) -> list[Neighbor]:
        """Embed ``text`` with the index provider, then :meth:`query`."""
        [vector] = self._provider.embed([text])
        return self.query(vector, k)

    def save(self, path: Path) -> None:
        """Persist the index to a JSON file (derived state; safe to delete)."""
        payload = {
            "provider": self._provider.name,
            "dimension": self._provider.dimension,
            "entries": self._entries,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    @classmethod
    def load(cls, path: Path, provider: EmbeddingProvider) -> EmbeddingIndex:
        """Reload an index, requiring ``provider`` to match the persisted space."""
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("index file is malformed")
        if payload.get("provider") != provider.name:
            raise ValueError(
                f"index was built with provider {payload.get('provider')!r}, "
                f"not {provider.name!r}"
            )
        raw_entries = payload.get("entries")
        if not isinstance(raw_entries, dict):
            raise ValueError("index file has no entries")
        entries = {
            str(cid): [float(value) for value in vec]
            for cid, vec in raw_entries.items()
        }
        return cls(provider, entries)


def _norm(vector: Vector) -> float:
    return math.sqrt(sum(value * value for value in vector))


def _cosine(a: Vector, norm_a: float, b: Vector, norm_b: float) -> float:
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return dot / (norm_a * norm_b)
