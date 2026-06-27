"""Tests for deterministic answer grading."""

from __future__ import annotations

from kosha.bench import BenchQuery, RetrievedContext, grade_query

_QUERY = BenchQuery(
    id="q",
    question="how long for a gold return",
    required_concepts=("policies/returns/gold-members",),
    answer_keywords=("45", "Gold"),
)


def _context(concept_ids: list[str]) -> RetrievedContext:
    return RetrievedContext("hybrid", concept_ids, text="", round_trips=1)


def test_required_concept_present_scores_full_recall() -> None:
    grade = grade_query(
        _QUERY, _context(["policies/returns/gold-members"]), "Gold members get 45 days."
    )
    assert grade.concept_recall == 1.0
    assert grade.answered is True
    assert grade.keyword_hits == 2
    assert grade.keyword_recall == 1.0


def test_missing_required_concept_scores_zero_recall() -> None:
    grade = grade_query(_QUERY, _context(["policies/shipping"]), "Shipping is 3-5 days.")
    assert grade.concept_recall == 0.0
    assert grade.answered is False


def test_keyword_matching_is_case_insensitive_and_partial() -> None:
    grade = grade_query(
        _QUERY, _context(["policies/returns/gold-members"]), "a gold customer: 45"
    )
    assert grade.keyword_hits == 2
    grade_partial = grade_query(
        _QUERY, _context(["policies/returns/gold-members"]), "only forty-five days"
    )
    assert grade_partial.keyword_hits == 0
