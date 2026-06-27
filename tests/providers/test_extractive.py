"""Tests for the deterministic extractive generation provider."""

from __future__ import annotations

from kosha.providers import ExtractiveGenerationProvider

_CONTEXT = (
    "Gold members have 45 days to return an item. "
    "Standard customers have 30 days. "
    "Shipping is handled by a third-party carrier."
)


def test_extracts_the_query_relevant_sentence() -> None:
    provider = ExtractiveGenerationProvider(max_sentences=1)
    answer = provider.generate("How long do gold members get to return?", _CONTEXT)
    assert "45 days" in answer.text
    assert "carrier" not in answer.text


def test_usage_counts_prompt_and_completion_tokens() -> None:
    provider = ExtractiveGenerationProvider(max_sentences=1)
    result = provider.generate("gold member return", _CONTEXT)
    assert result.usage.prompt_tokens > 0
    assert result.usage.completion_tokens > 0
    assert result.usage.total_tokens == (
        result.usage.prompt_tokens + result.usage.completion_tokens
    )


def test_generation_is_deterministic() -> None:
    provider = ExtractiveGenerationProvider()
    a = provider.generate("return window", _CONTEXT)
    b = provider.generate("return window", _CONTEXT)
    assert a == b
