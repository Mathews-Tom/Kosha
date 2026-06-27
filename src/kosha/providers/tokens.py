"""Text tokenization helpers shared by providers and the benchmark.

``count_tokens`` is a deterministic, model-neutral approximation of token count
(word + standalone-punctuation segments). It is not a specific model's tokenizer;
the benchmark uses it only for *relative* token comparisons across strategies, and
reports state the method. ``tokenize`` is the lowercase alphanumeric tokenizer the
lexical embedding and extractive generation share.
"""

from __future__ import annotations

import re

# A "token" for counting: a run of word characters, or a single punctuation mark.
_COUNT_TOKEN = re.compile(r"\w+|[^\w\s]")
# A "term" for lexical similarity: a lowercase alphanumeric run.
_TERM = re.compile(r"[a-z0-9]+")


def count_tokens(text: str) -> int:
    """Return an approximate token count for ``text`` (deterministic)."""
    return len(_COUNT_TOKEN.findall(text))


def tokenize(text: str) -> list[str]:
    """Return lowercase alphanumeric terms in ``text``, in order."""
    return _TERM.findall(text.lower())
