"""Retrieval strategies compared by the Premise-Validation spike.

Each strategy turns a query into a :class:`RetrievedContext`: the concept set whose
content reaches the generator, the assembled context text, and the number of
sequential *retrieval* model round-trips it costs (the structural latency driver —
generation adds one further call for every strategy).

* :class:`HybridStrategy` — Kosha's path: one embedding **jump** to candidate
  concepts, then a local **traverse** along out-links to expand. Production-leaning;
  reuses the embedding index.
* :class:`RagStrategy` — benchmark-only: embed fixed-size body chunks once, retrieve
  the top-k chunks per query.
* :class:`LongContextStrategy` — benchmark-only: put every concept body in context.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from kosha.index import EmbeddingIndex
from kosha.model import Bundle, Concept
from kosha.providers.base import EmbeddingProvider, Vector

# Joins concept documents / chunks within an assembled context.
_JOIN = "\n\n"


@dataclass(frozen=True)
class RetrievedContext:
    """What a strategy assembled for one query."""

    strategy: str
    concept_ids: list[str]
    text: str
    round_trips: int


class RetrievalStrategy(Protocol):
    """Assembles context for a query."""

    @property
    def name(self) -> str: ...

    def retrieve(self, query: str) -> RetrievedContext: ...


class HybridStrategy:
    """Embedding-jump to candidate concepts, then traverse out-links to expand."""

    def __init__(
        self,
        bundle: Bundle,
        index: EmbeddingIndex,
        *,
        jump_k: int = 3,
        max_concepts: int = 6,
    ) -> None:
        if jump_k <= 0 or max_concepts <= 0:
            raise ValueError("jump_k and max_concepts must be positive")
        self._bundle = bundle
        self._index = index
        self._jump_k = jump_k
        self._max_concepts = max_concepts

    @property
    def name(self) -> str:
        return "hybrid"

    def retrieve(self, query: str) -> RetrievedContext:
        # Jump: one embedding round-trip lands near the answer.
        seeds = [n.concept_id for n in self._index.query_text(query, self._jump_k)]
        # Traverse: visit each candidate and immediately expand its out-links
        # (local, no model call), so the top candidate's neighborhood is preferred.
        ordered: list[str] = []
        for cid in seeds:
            _append_unique(ordered, cid)
            concept = self._bundle.concepts.get(cid)
            if concept is None:
                continue
            for target in concept.out_links:
                if target in self._bundle.concepts:
                    _append_unique(ordered, target)
        loaded = ordered[: self._max_concepts]
        text = _JOIN.join(_document(self._bundle.concepts[cid]) for cid in loaded)
        return RetrievedContext(self.name, loaded, text, round_trips=1)


class RagStrategy:
    """Chunk every concept body once, retrieve the top-k chunks per query."""

    def __init__(
        self,
        bundle: Bundle,
        provider: EmbeddingProvider,
        *,
        chunk_words: int = 60,
        top_k: int = 5,
    ) -> None:
        if chunk_words <= 0 or top_k <= 0:
            raise ValueError("chunk_words and top_k must be positive")
        self._provider = provider
        self._top_k = top_k
        self._chunks: list[_Chunk] = _chunk_bundle(bundle, chunk_words)
        vectors = provider.embed([c.text for c in self._chunks]) if self._chunks else []
        self._vectors: list[Vector] = vectors

    @property
    def name(self) -> str:
        return "rag"

    def retrieve(self, query: str) -> RetrievedContext:
        # One embedding round-trip; chunk vectors were embedded at build time.
        [query_vec] = self._provider.embed([query])
        ranked = sorted(
            range(len(self._chunks)),
            key=lambda i: (-_cosine(query_vec, self._vectors[i]), i),
        )
        chosen = ranked[: self._top_k]
        concept_ids: list[str] = []
        for i in chosen:
            _append_unique(concept_ids, self._chunks[i].concept_id)
        text = _JOIN.join(self._chunks[i].text for i in chosen)
        return RetrievedContext(self.name, concept_ids, text, round_trips=1)


class LongContextStrategy:
    """Put every concept body in context — no retrieval."""

    def __init__(self, bundle: Bundle) -> None:
        self._concept_ids = sorted(bundle.concepts)
        self._text = _JOIN.join(
            _document(bundle.concepts[cid]) for cid in self._concept_ids
        )

    @property
    def name(self) -> str:
        return "long_context"

    def retrieve(self, query: str) -> RetrievedContext:
        return RetrievedContext(
            self.name, list(self._concept_ids), self._text, round_trips=0
        )


@dataclass(frozen=True)
class _Chunk:
    concept_id: str
    text: str


def _document(concept: Concept) -> str:
    return concept.body.strip()


def _chunk_bundle(bundle: Bundle, chunk_words: int) -> list[_Chunk]:
    chunks: list[_Chunk] = []
    for cid in sorted(bundle.concepts):
        words = _document(bundle.concepts[cid]).split()
        for start in range(0, len(words), chunk_words):
            piece = " ".join(words[start : start + chunk_words])
            if piece:
                chunks.append(_Chunk(cid, piece))
    return chunks


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _cosine(a: Vector, b: Vector) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = (sum(x * x for x in a) ** 0.5) * (sum(y * y for y in b) ** 0.5)
    return dot / norm if norm else 0.0
