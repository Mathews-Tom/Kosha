"""Resolve providers from the environment (opt-in, fail-loud).

Defaults are the deterministic local providers so the benchmark runs offline and
reproducibly. Setting ``KOSHA_EMBED_BASE_URL`` (resp. ``KOSHA_GEN_BASE_URL``)
opts into the OpenAI-compatible HTTP provider; a base URL without its companion
model variable is an error rather than a silent fallback.

Environment variables
---------------------
* ``KOSHA_EMBED_BASE_URL`` / ``KOSHA_EMBED_MODEL`` / ``KOSHA_EMBED_API_KEY``
  / ``KOSHA_EMBED_DIM`` (default 1536)
* ``KOSHA_GEN_BASE_URL`` / ``KOSHA_GEN_MODEL`` / ``KOSHA_GEN_API_KEY``
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from kosha.providers.base import EmbeddingProvider, GenerationProvider
from kosha.providers.extractive import ExtractiveGenerationProvider
from kosha.providers.lexical import LexicalEmbeddingProvider
from kosha.providers.openai_compatible import (
    OpenAICompatibleEmbeddingProvider,
    OpenAICompatibleGenerationProvider,
)

_DEFAULT_EMBED_DIM = 1536


def resolve_embedding_provider(
    env: Mapping[str, str] | None = None,
) -> EmbeddingProvider:
    """Return the configured embedding provider (lexical local default)."""
    source = os.environ if env is None else env
    base_url = source.get("KOSHA_EMBED_BASE_URL", "").strip()
    if not base_url:
        return LexicalEmbeddingProvider()
    model = source.get("KOSHA_EMBED_MODEL", "").strip()
    if not model:
        raise ValueError("KOSHA_EMBED_BASE_URL is set but KOSHA_EMBED_MODEL is missing")
    return OpenAICompatibleEmbeddingProvider(
        base_url=base_url,
        api_key=source.get("KOSHA_EMBED_API_KEY", ""),
        model=model,
        dimension=_int_env(source, "KOSHA_EMBED_DIM", _DEFAULT_EMBED_DIM),
    )


def resolve_generation_provider(
    env: Mapping[str, str] | None = None,
) -> GenerationProvider:
    """Return the configured generation provider (extractive local default)."""
    source = os.environ if env is None else env
    base_url = source.get("KOSHA_GEN_BASE_URL", "").strip()
    if not base_url:
        return ExtractiveGenerationProvider()
    model = source.get("KOSHA_GEN_MODEL", "").strip()
    if not model:
        raise ValueError("KOSHA_GEN_BASE_URL is set but KOSHA_GEN_MODEL is missing")
    return OpenAICompatibleGenerationProvider(
        base_url=base_url,
        api_key=source.get("KOSHA_GEN_API_KEY", ""),
        model=model,
    )


def _int_env(source: Mapping[str, str], key: str, default: int) -> int:
    raw = source.get(key, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{key} must be an integer, got {raw!r}") from exc
