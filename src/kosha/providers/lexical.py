"""A deterministic, dependency-free lexical embedding provider.

Embeddings are built with the hashing-vectorizer trick: each term is hashed to a
fixed dimension and accumulated as a term-frequency count, then the vector is
L2-normalized so cosine similarity reflects lexical overlap. This is a real local
embedding suitable for small bundles and offline/CI runs; it carries no model
weights and produces identical vectors across machines and runs (BLAKE2b is stable,
unlike Python's salted ``hash``). For semantic embeddings, configure the
env-driven OpenAI-compatible provider instead.
"""

from __future__ import annotations

import hashlib
import math

from kosha.providers.base import Vector
from kosha.providers.tokens import tokenize


class LexicalEmbeddingProvider:
    """Hashing term-frequency embeddings with L2-normalized cosine geometry."""

    def __init__(self, dimension: int = 256) -> None:
        if dimension <= 0:
            raise ValueError("dimension must be positive")
        self._dimension = dimension

    @property
    def name(self) -> str:
        return f"lexical-hash-{self._dimension}"

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: list[str]) -> list[Vector]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> Vector:
        vec = [0.0] * self._dimension
        for term in tokenize(text):
            digest = hashlib.blake2b(term.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest, "big") % self._dimension
            vec[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vec))
        if norm == 0.0:
            return vec
        return [value / norm for value in vec]
