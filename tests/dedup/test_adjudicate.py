"""Tests for ambiguous-band adjudication (lexical + generation paths)."""

from __future__ import annotations

import pytest

from kosha.dedup.adjudicate import (
    GenerationAdjudicator,
    LexicalAdjudicator,
    Verdict,
    build_adjudication_prompt,
    parse_verdict,
)
from kosha.providers.base import Generation, Usage

_OVERSCOPED = "# A\nt\n# B\nt\n# C\nt\n# D\nt\n# E\nt\n# F\nt\n# G\nt\n# H\nt\n# I\nt"


class _CannedGenerator:
    """A generation provider that returns a fixed answer (real protocol impl)."""

    def __init__(self, answer: str) -> None:
        self._answer = answer

    @property
    def name(self) -> str:
        return "canned"

    def generate(self, query: str, context: str) -> Generation:
        return Generation(text=self._answer, usage=Usage(prompt_tokens=1, completion_tokens=1))


def test_lexical_splits_an_overscoped_draft() -> None:
    adj = LexicalAdjudicator()
    result = adj.adjudicate(_OVERSCOPED, "anything")
    assert result.verdict is Verdict.SPLIT
    assert "granularity" in result.rationale


def test_lexical_calls_high_overlap_same() -> None:
    adj = LexicalAdjudicator(same_threshold=0.4)
    result = adj.adjudicate(
        "Gold members may return an item within 45 days.",
        "Gold members may return an item within 45 days of delivery.",
    )
    assert result.verdict is Verdict.SAME
    assert "jaccard" in result.rationale


def test_lexical_calls_low_overlap_different() -> None:
    adj = LexicalAdjudicator(same_threshold=0.4)
    result = adj.adjudicate("Standard shipping takes three days.", "Refunds post to the card.")
    assert result.verdict is Verdict.DIFFERENT


def test_lexical_adjudicator_is_deterministic() -> None:
    adj = LexicalAdjudicator()
    a = adj.adjudicate("return window policy", "return window rule")
    b = adj.adjudicate("return window policy", "return window rule")
    assert a == b


def test_lexical_rejects_out_of_range_threshold() -> None:
    with pytest.raises(ValueError, match="same_threshold"):
        LexicalAdjudicator(same_threshold=1.5)


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("same", Verdict.SAME),
        ("Different.", Verdict.DIFFERENT),
        ("SPLIT", Verdict.SPLIT),
        ("These are the same concept.", Verdict.SAME),
        ("They look the same but are split across topics", Verdict.SPLIT),
    ],
)
def test_parse_verdict_extracts_keyword(answer: str, expected: Verdict) -> None:
    assert parse_verdict(answer) == expected


def test_parse_verdict_rejects_a_verdict_free_response() -> None:
    with pytest.raises(ValueError, match="no verdict"):
        parse_verdict("I am not sure about this one")


def test_adjudication_prompt_carries_both_concepts_and_the_instruction() -> None:
    query, context = build_adjudication_prompt("DRAFT_TEXT", "CANDIDATE_TEXT")
    assert "same, different, or split" in query
    assert "DRAFT_TEXT" in context
    assert "CANDIDATE_TEXT" in context


def test_generation_adjudicator_parses_the_model_verdict() -> None:
    adj = GenerationAdjudicator(_CannedGenerator("different"))
    result = adj.adjudicate("a", "b")
    assert result.verdict is Verdict.DIFFERENT
    assert adj.name == "generation:canned"
    assert "different" in result.rationale


def test_generation_adjudicator_propagates_an_unparseable_verdict() -> None:
    adj = GenerationAdjudicator(_CannedGenerator("no idea"))
    with pytest.raises(ValueError, match="no verdict"):
        adj.adjudicate("a", "b")
