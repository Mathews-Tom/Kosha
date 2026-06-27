"""Tests for env-driven provider resolution."""

from __future__ import annotations

import pytest

from kosha.providers import (
    ExtractiveGenerationProvider,
    LexicalEmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
    OpenAICompatibleGenerationProvider,
    resolve_embedding_provider,
    resolve_generation_provider,
)


def test_empty_env_defaults_to_local_providers() -> None:
    assert isinstance(resolve_embedding_provider({}), LexicalEmbeddingProvider)
    assert isinstance(resolve_generation_provider({}), ExtractiveGenerationProvider)


def test_embed_base_url_selects_http_provider() -> None:
    provider = resolve_embedding_provider(
        {
            "KOSHA_EMBED_BASE_URL": "https://api.example.com/v1",
            "KOSHA_EMBED_MODEL": "text-embed-3",
            "KOSHA_EMBED_DIM": "512",
        }
    )
    assert isinstance(provider, OpenAICompatibleEmbeddingProvider)
    assert provider.name == "openai:text-embed-3"
    assert provider.dimension == 512


def test_gen_base_url_selects_http_provider() -> None:
    provider = resolve_generation_provider(
        {
            "KOSHA_GEN_BASE_URL": "https://api.example.com/v1",
            "KOSHA_GEN_MODEL": "gpt-mini",
        }
    )
    assert isinstance(provider, OpenAICompatibleGenerationProvider)
    assert provider.name == "openai:gpt-mini"


def test_base_url_without_model_fails_loudly() -> None:
    with pytest.raises(ValueError, match="KOSHA_EMBED_MODEL"):
        resolve_embedding_provider({"KOSHA_EMBED_BASE_URL": "https://x/v1"})
    with pytest.raises(ValueError, match="KOSHA_GEN_MODEL"):
        resolve_generation_provider({"KOSHA_GEN_BASE_URL": "https://x/v1"})


def test_non_integer_dimension_is_rejected() -> None:
    with pytest.raises(ValueError, match="KOSHA_EMBED_DIM"):
        resolve_embedding_provider(
            {
                "KOSHA_EMBED_BASE_URL": "https://x/v1",
                "KOSHA_EMBED_MODEL": "m",
                "KOSHA_EMBED_DIM": "not-a-number",
            }
        )
