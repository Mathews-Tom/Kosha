"""Provider protocols and the small value types they exchange."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

# A dense embedding vector. Plain ``list[float]`` keeps the interface dependency-free;
# callers that want numpy can convert at the edge.
Vector = list[float]


@dataclass(frozen=True)
class Usage:
    """Token accounting for one generation call."""

    prompt_tokens: int
    completion_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True)
class Generation:
    """The result of a generation call: the answer text plus token usage."""

    text: str
    usage: Usage


class EmbeddingProvider(Protocol):
    """Turns text into dense vectors for nearest-neighbor retrieval."""

    @property
    def name(self) -> str:
        """Stable identifier recorded in reports (e.g. ``lexical-hash-256``)."""
        ...

    @property
    def dimension(self) -> int:
        """Vector dimensionality every :meth:`embed` result has."""
        ...

    def embed(self, texts: list[str]) -> list[Vector]:
        """Embed a batch of texts, returning one vector per input in order."""
        ...


class GenerationProvider(Protocol):
    """Answers a query given retrieved context, reporting token usage."""

    @property
    def name(self) -> str:
        """Stable identifier recorded in reports (e.g. ``extractive``)."""
        ...

    def generate(self, query: str, context: str) -> Generation:
        """Produce an answer to ``query`` grounded in ``context``."""
        ...
