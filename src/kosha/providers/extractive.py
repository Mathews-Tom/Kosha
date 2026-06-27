"""A deterministic, dependency-free extractive generation provider.

It answers a query by selecting the context sentences with the highest lexical
overlap with the query — a real (if simple) extractive QA step that lets the
benchmark run an end-to-end answer pipeline offline and count completion tokens.
For abstractive answers from a real model, configure the env-driven
OpenAI-compatible provider instead.
"""

from __future__ import annotations

import re

from kosha.providers.base import Generation, Usage
from kosha.providers.tokens import count_tokens, tokenize

# Sentence boundary: terminal punctuation followed by whitespace.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


class ExtractiveGenerationProvider:
    """Returns the query-relevant sentences from the supplied context."""

    def __init__(self, max_sentences: int = 3) -> None:
        if max_sentences <= 0:
            raise ValueError("max_sentences must be positive")
        self._max_sentences = max_sentences

    @property
    def name(self) -> str:
        return f"extractive-{self._max_sentences}"

    def generate(self, query: str, context: str) -> Generation:
        query_terms = set(tokenize(query))
        sentences = [s.strip() for s in _SENTENCE_SPLIT.split(context) if s.strip()]
        ranked = sorted(
            enumerate(sentences),
            key=lambda item: (-_overlap(item[1], query_terms), item[0]),
        )
        chosen = sorted(idx for idx, _ in ranked[: self._max_sentences])
        answer = " ".join(sentences[idx] for idx in chosen)
        usage = Usage(
            prompt_tokens=count_tokens(query) + count_tokens(context),
            completion_tokens=count_tokens(answer),
        )
        return Generation(text=answer, usage=usage)


def _overlap(sentence: str, query_terms: set[str]) -> int:
    """Count distinct query terms that appear in ``sentence``."""
    return len(set(tokenize(sentence)) & query_terms)
