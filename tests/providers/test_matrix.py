"""Resolving the Gate-0 v2 provider matrix from the environment (spike S2)."""

from __future__ import annotations

import json

import pytest

from kosha.providers.extractive import ExtractiveGenerationProvider
from kosha.providers.lexical import LexicalEmbeddingProvider
from kosha.providers.matrix import resolve_provider_matrix
from kosha.providers.openai_compatible import (
    OpenAICompatibleEmbeddingProvider,
    OpenAICompatibleGenerationProvider,
)


def test_no_env_falls_back_to_single_local_pair() -> None:
    matrix = resolve_provider_matrix({})
    assert len(matrix.embeddings) == 1
    assert len(matrix.generations) == 1
    assert isinstance(matrix.embeddings[0][1], LexicalEmbeddingProvider)
    assert isinstance(matrix.generations[0][1], ExtractiveGenerationProvider)
    assert matrix.cell_count == 1


def test_local_entries_build_a_labeled_offline_matrix() -> None:
    spec = {
        "embeddings": [{"label": "lex-a"}, {"label": "lex-b"}],
        "generations": [{"label": "ext-a"}, {"label": "ext-b"}],
    }
    matrix = resolve_provider_matrix({"KOSHA_GATE2_MATRIX": json.dumps(spec)})
    assert matrix.embedding_labels == ("lex-a", "lex-b")
    assert matrix.generation_labels == ("ext-a", "ext-b")
    assert matrix.cell_count == 4
    assert all(isinstance(provider, LexicalEmbeddingProvider) for _, provider in matrix.embeddings)


def test_http_entries_build_openai_compatible_providers() -> None:
    spec = {
        "embeddings": [
            {
                "label": "bge-m3",
                "base_url": "http://localhost:11434/v1",
                "model": "bge-m3",
                "dim": 1024,
            }
        ],
        "generations": [
            {
                "label": "gpt-4o-mini",
                "base_url": "https://openrouter.ai/api/v1",
                "model": "openai/gpt-4o-mini",
                "api_key_env": "OR_KEY",
            }
        ],
    }
    env = {"KOSHA_GATE2_MATRIX": json.dumps(spec), "OR_KEY": "secret-token"}
    matrix = resolve_provider_matrix(env)
    embed = matrix.embeddings[0][1]
    gen = matrix.generations[0][1]
    assert isinstance(embed, OpenAICompatibleEmbeddingProvider)
    assert embed.dimension == 1024
    assert isinstance(gen, OpenAICompatibleGenerationProvider)


def test_invalid_json_is_rejected() -> None:
    with pytest.raises(ValueError, match="not valid JSON"):
        resolve_provider_matrix({"KOSHA_GATE2_MATRIX": "{not json"})


def test_http_entry_without_model_is_rejected() -> None:
    spec = {
        "embeddings": [{"label": "x", "base_url": "http://localhost:11434/v1"}],
        "generations": [{"label": "g"}],
    }
    with pytest.raises(ValueError, match="no model"):
        resolve_provider_matrix({"KOSHA_GATE2_MATRIX": json.dumps(spec)})


def test_non_integer_dim_is_rejected() -> None:
    spec = {
        "embeddings": [
            {"label": "x", "base_url": "http://h/v1", "model": "m", "dim": "big"}
        ],
        "generations": [{"label": "g"}],
    }
    with pytest.raises(ValueError, match="dim must be an integer"):
        resolve_provider_matrix({"KOSHA_GATE2_MATRIX": json.dumps(spec)})


def test_empty_lists_are_rejected() -> None:
    spec = {"embeddings": [], "generations": []}
    with pytest.raises(ValueError, match="at least one embedding"):
        resolve_provider_matrix({"KOSHA_GATE2_MATRIX": json.dumps(spec)})
