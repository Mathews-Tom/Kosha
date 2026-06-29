"""Resolve a provider *matrix* for the Gate-0 v2 re-test (spike S2).

Gate-0 v2 measures each axis across at least two embeddings and two generation
models so a win cannot be an artifact of one model (KOSHA_STRATEGIC_ANALYSIS
§2.4). This module turns one environment variable into the labeled provider lists
the harness iterates.

Environment
-----------
``KOSHA_GATE2_MATRIX`` holds a JSON object::

    {
      "embeddings": [
        {"label": "bge-m3", "base_url": "http://localhost:11434/v1",
         "model": "bge-m3", "dim": 1024},
        {"label": "nomic", "base_url": "http://localhost:11434/v1",
         "model": "nomic-embed-text", "dim": 768}
      ],
      "generations": [
        {"label": "gpt-4o-mini", "base_url": "https://openrouter.ai/api/v1",
         "model": "openai/gpt-4o-mini", "api_key_env": "OPENROUTER_API_KEY"},
        {"label": "gemma4", "base_url": "http://localhost:11434/v1",
         "model": "gemma4:12b-mlx"}
      ]
    }

An entry with no ``base_url`` resolves to the deterministic local provider
(lexical embedding / extractive generation), which keeps an offline 1x1 matrix
runnable. ``api_key_env`` names an environment variable to read the key from so
secrets never live in the spec. When ``KOSHA_GATE2_MATRIX`` is absent the matrix
falls back to the single provider pair from :mod:`kosha.providers.factory` — a
1x1 matrix that the Gate-0 v2 criterion will (correctly) flag as underpowered.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass

from kosha.providers.base import EmbeddingProvider, GenerationProvider
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

_MATRIX_ENV = "KOSHA_GATE2_MATRIX"
_DEFAULT_EMBED_DIM = 1536


@dataclass(frozen=True)
class ProviderMatrix:
    """Labeled embedding x generation providers for the Gate-0 v2 re-test."""

    embeddings: tuple[tuple[str, EmbeddingProvider], ...]
    generations: tuple[tuple[str, GenerationProvider], ...]

    @property
    def embedding_labels(self) -> tuple[str, ...]:
        return tuple(label for label, _ in self.embeddings)

    @property
    def generation_labels(self) -> tuple[str, ...]:
        return tuple(label for label, _ in self.generations)

    @property
    def cell_count(self) -> int:
        return len(self.embeddings) * len(self.generations)


def resolve_provider_matrix(env: Mapping[str, str] | None = None) -> ProviderMatrix:
    """Build the provider matrix from ``KOSHA_GATE2_MATRIX`` or the single pair."""
    source = os.environ if env is None else env
    raw = source.get(_MATRIX_ENV, "").strip()
    if not raw:
        embed = resolve_embedding_provider(env)
        gen = resolve_generation_provider(env)
        return ProviderMatrix(
            embeddings=((embed.name, embed),),
            generations=((gen.name, gen),),
        )
    spec = _parse_spec(raw)
    embeddings = tuple(
        _embedding_entry(entry, source) for entry in _entries(spec, "embeddings")
    )
    generations = tuple(
        _generation_entry(entry, source) for entry in _entries(spec, "generations")
    )
    if not embeddings or not generations:
        raise ValueError(f"{_MATRIX_ENV} must list at least one embedding and one generation")
    return ProviderMatrix(embeddings=embeddings, generations=generations)


def _parse_spec(raw: str) -> Mapping[str, object]:
    try:
        spec = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{_MATRIX_ENV} is not valid JSON: {exc}") from exc
    if not isinstance(spec, dict):
        raise ValueError(f"{_MATRIX_ENV} must be a JSON object")
    return spec


def _entries(spec: Mapping[str, object], key: str) -> list[Mapping[str, object]]:
    value = spec.get(key, [])
    if not isinstance(value, list):
        raise ValueError(f"{_MATRIX_ENV}.{key} must be a list")
    entries: list[Mapping[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError(f"{_MATRIX_ENV}.{key} entries must be objects")
        entries.append(item)
    return entries


def _embedding_entry(
    entry: Mapping[str, object], source: Mapping[str, str]
) -> tuple[str, EmbeddingProvider]:
    label = _require_label(entry, "embeddings")
    base_url = _str(entry, "base_url")
    if not base_url:
        return label, LexicalEmbeddingProvider()
    provider = OpenAICompatibleEmbeddingProvider(
        base_url=base_url,
        api_key=_api_key(entry, source),
        model=_require_model(entry, label),
        dimension=_dim(entry),
    )
    return label, provider


def _generation_entry(
    entry: Mapping[str, object], source: Mapping[str, str]
) -> tuple[str, GenerationProvider]:
    label = _require_label(entry, "generations")
    base_url = _str(entry, "base_url")
    if not base_url:
        return label, ExtractiveGenerationProvider()
    provider = OpenAICompatibleGenerationProvider(
        base_url=base_url,
        api_key=_api_key(entry, source),
        model=_require_model(entry, label),
    )
    return label, provider


def _require_label(entry: Mapping[str, object], key: str) -> str:
    label = _str(entry, "label")
    if not label:
        raise ValueError(f"{_MATRIX_ENV}.{key} entry is missing a label")
    return label


def _require_model(entry: Mapping[str, object], label: str) -> str:
    model = _str(entry, "model")
    if not model:
        raise ValueError(f"{_MATRIX_ENV} entry {label!r} has a base_url but no model")
    return model


def _api_key(entry: Mapping[str, object], source: Mapping[str, str]) -> str:
    key_env = _str(entry, "api_key_env")
    if key_env:
        return source.get(key_env, "")
    return _str(entry, "api_key")


def _dim(entry: Mapping[str, object]) -> int:
    value = entry.get("dim")
    if value is None:
        return _DEFAULT_EMBED_DIM
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{_MATRIX_ENV} dim must be an integer, got {value!r}")
    return value


def _str(entry: Mapping[str, object], key: str) -> str:
    value = entry.get(key, "")
    if not isinstance(value, str):
        raise ValueError(f"{_MATRIX_ENV} field {key!r} must be a string, got {value!r}")
    return value.strip()
