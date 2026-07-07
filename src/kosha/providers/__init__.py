"""Model-neutral provider interfaces and concrete providers.

Embeddings and generation sit behind narrow protocols (system_design §1:
model- and cloud-neutral) so the maintenance loop and the benchmark harness never
depend on a specific model or vendor. Two concrete providers ship:

* a deterministic, zero-dependency **local** pair (:class:`LexicalEmbeddingProvider`,
  :class:`ExtractiveGenerationProvider`) used as the default and in tests, and
* an **env-configured** OpenAI-compatible HTTP pair that talks to any
  ``/embeddings`` + ``/chat/completions`` endpoint (OpenAI, Ollama, llama.cpp, …)
  over the standard library only.

:func:`resolve_embedding_provider` / :func:`resolve_generation_provider` pick the
provider from the environment, defaulting to the local pair so the benchmark runs
offline and reproducibly.
"""

from __future__ import annotations

from kosha.providers.base import (
    EmbeddingProvider,
    Generation,
    GenerationProvider,
    Usage,
    Vector,
)
from kosha.providers.diagnostics import (
    EnvVarDiagnostic,
    ProviderDiagnostic,
    diagnose_embedding_provider,
    diagnose_generation_provider,
)
from kosha.providers.extractive import ExtractiveGenerationProvider
from kosha.providers.factory import (
    resolve_embedding_provider,
    resolve_generation_provider,
)
from kosha.providers.lexical import LexicalEmbeddingProvider
from kosha.providers.openai_compatible import (
    OpenAICompatibleEmbeddingProvider,
    OpenAICompatibleGenerationProvider,
)
from kosha.providers.tokens import count_tokens, tokenize

__all__ = [
    "EmbeddingProvider",
    "EnvVarDiagnostic",
    "ExtractiveGenerationProvider",
    "Generation",
    "GenerationProvider",
    "LexicalEmbeddingProvider",
    "OpenAICompatibleEmbeddingProvider",
    "OpenAICompatibleGenerationProvider",
    "ProviderDiagnostic",
    "Usage",
    "Vector",
    "count_tokens",
    "diagnose_embedding_provider",
    "diagnose_generation_provider",
    "resolve_embedding_provider",
    "resolve_generation_provider",
    "tokenize",
]
