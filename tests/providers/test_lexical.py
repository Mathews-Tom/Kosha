"""Tests for the deterministic lexical embedding provider."""

from __future__ import annotations

import math

import pytest

from kosha.providers import LexicalEmbeddingProvider, Vector


def _cosine(a: Vector, b: Vector) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_embeddings_are_deterministic_across_calls() -> None:
    provider = LexicalEmbeddingProvider()
    first = provider.embed(["gold member return window"])
    second = provider.embed(["gold member return window"])
    assert first == second


def test_embeddings_have_the_declared_dimension_and_unit_norm() -> None:
    provider = LexicalEmbeddingProvider(dimension=64)
    [vector] = provider.embed(["a non-empty sentence"])
    assert len(vector) == 64
    assert provider.dimension == 64
    assert math.isclose(math.sqrt(sum(v * v for v in vector)), 1.0, rel_tol=1e-9)


def test_lexically_similar_text_is_closer_than_dissimilar_text() -> None:
    provider = LexicalEmbeddingProvider()
    query, near, far = provider.embed(
        [
            "how long is the gold member return window",
            "gold members get a longer return window",
            "expedited shipping carrier delivery fees",
        ]
    )
    assert _cosine(query, near) > _cosine(query, far)


def test_empty_text_yields_a_zero_vector() -> None:
    provider = LexicalEmbeddingProvider(dimension=16)
    [vector] = provider.embed([""])
    assert vector == [0.0] * 16


def test_non_positive_dimension_is_rejected() -> None:
    with pytest.raises(ValueError, match="dimension"):
        LexicalEmbeddingProvider(dimension=0)
