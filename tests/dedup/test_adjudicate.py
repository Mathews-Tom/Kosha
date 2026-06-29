"""Tests for ambiguous-band adjudication (lexical + generation paths)."""

from __future__ import annotations

import pytest

from kosha.dedup.adjudicate import (
    CandidateConcept,
    GenerationAdjudicator,
    LexicalAdjudicator,
    Verdict,
    build_adjudication_prompt,
    build_selection_prompt,
    parse_selection,
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


def test_lexical_select_picks_the_highest_overlap_candidate() -> None:
    adj = LexicalAdjudicator(same_threshold=0.4)
    candidates = [
        CandidateConcept("c-refund", "Refunds post to the original card after approval."),
        CandidateConcept("c-gold", "Gold members may return an item within 45 days of delivery."),
    ]
    result = adj.select("Gold members may return an item within 45 days.", candidates)
    assert result.verdict is Verdict.SAME
    assert result.concept_id == "c-gold"


def test_lexical_select_creates_when_no_candidate_overlaps() -> None:
    adj = LexicalAdjudicator(same_threshold=0.4)
    candidates = [CandidateConcept("c-refund", "Refunds post to the original card.")]
    result = adj.select("Membership tiers grant escalating loyalty perks.", candidates)
    assert result.verdict is Verdict.DIFFERENT
    assert result.concept_id is None


def test_lexical_select_splits_an_overscoped_draft() -> None:
    adj = LexicalAdjudicator()
    result = adj.select(_OVERSCOPED, [CandidateConcept("c", "anything at all")])
    assert result.verdict is Verdict.SPLIT
    assert result.concept_id is None


def test_generation_select_chooses_the_named_concept_id() -> None:
    adj = GenerationAdjudicator(_CannedGenerator("UPDATE json/dumps"))
    candidates = [
        CandidateConcept("json/loads", "Parse JSON text into Python objects."),
        CandidateConcept("json/dumps", "Serialize a value to JSON text."),
    ]
    result = adj.select("Convert a value into a JSON-formatted string.", candidates)
    assert result.verdict is Verdict.SAME
    assert result.concept_id == "json/dumps"


def test_generation_select_creates_on_create() -> None:
    adj = GenerationAdjudicator(_CannedGenerator("CREATE"))
    candidates = [CandidateConcept("json/dumps", "Serialize a value to JSON text.")]
    result = adj.select("Load a CSV into a pandas DataFrame.", candidates)
    assert result.verdict is Verdict.DIFFERENT
    assert result.concept_id is None


def test_generation_select_creates_on_an_unparseable_response() -> None:
    # An answer with no 'UPDATE <id>' falls to CREATE, never attaches blindly.
    adj = GenerationAdjudicator(_CannedGenerator("maybe the first item, unsure"))
    candidates = [CandidateConcept("json/dumps", "Serialize a value to JSON text.")]
    result = adj.select("x", candidates)
    assert result.verdict is Verdict.DIFFERENT
    assert result.concept_id is None


def test_generation_select_creates_when_the_named_id_is_unknown() -> None:
    adj = GenerationAdjudicator(_CannedGenerator("UPDATE made/up"))
    candidates = [CandidateConcept("json/dumps", "Serialize a value to JSON text.")]
    result = adj.select("Serialize to JSON.", candidates)
    assert result.verdict is Verdict.DIFFERENT
    assert result.concept_id is None


def test_generation_select_splits_an_overscoped_draft_without_the_llm() -> None:
    # Granularity is decided deterministically, so a never-answering generator is fine.
    adj = GenerationAdjudicator(_CannedGenerator("UPDATE json/dumps"))
    candidates = [CandidateConcept("json/dumps", "Serialize a value to JSON text.")]
    result = adj.select(_OVERSCOPED, candidates)
    assert result.verdict is Verdict.SPLIT
    assert result.concept_id is None


def test_selection_prompt_lists_candidate_ids_and_asks_for_update_or_create() -> None:
    candidates = [
        CandidateConcept("json/dumps", "Serialize a value to JSON text."),
        CandidateConcept("json/loads", "Parse JSON text into Python objects."),
    ]
    query, context = build_selection_prompt("DRAFT_TEXT", candidates)
    assert "json/dumps" in context and "json/loads" in context
    assert "DRAFT_TEXT" in context
    assert "UPDATE" in query and "CREATE" in query


def test_parse_selection_reads_an_update_with_a_candidate_id() -> None:
    result = parse_selection("UPDATE re/findall", ["re/find", "re/findall"], "gen")
    assert result.verdict is Verdict.SAME
    assert result.concept_id == "re/findall"


def test_parse_selection_tolerates_brackets_around_the_id() -> None:
    # gpt-4o-mini echoes the candidate id in the bracket form it was shown.
    result = parse_selection("UPDATE [json/dumps]", ["json/loads", "json/dumps"], "gen")
    assert result.verdict is Verdict.SAME
    assert result.concept_id == "json/dumps"


def test_contradiction_routes_to_the_owning_concept_not_create() -> None:
    # Routing is on topic identity, not agreement: a conflicting restatement of
    # findall shares its vocabulary, so it selects re/findall (-> UPDATE ->
    # reconcile) instead of being mis-filed as a new concept.
    adj = LexicalAdjudicator(same_threshold=0.2)
    candidates = [
        CandidateConcept("c-refund", "Refunds post to the original card after approval."),
        CandidateConcept(
            "re/findall", "findall returns every non-overlapping match of a regular expression."
        ),
    ]
    selection = adj.select(
        "findall now returns only the first match of a regular expression.", candidates
    )
    assert selection.verdict is Verdict.SAME
    assert selection.concept_id == "re/findall"


def test_selection_prompt_routes_contradictions_to_update() -> None:
    query, _ = build_selection_prompt(
        "x", [CandidateConcept("re/findall", "find all matches")]
    )
    assert "contradicts" in query.lower()
    assert "UPDATE" in query
