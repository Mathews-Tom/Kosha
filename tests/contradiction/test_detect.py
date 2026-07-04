"""Contradiction detector: structured diff + judge + finder (M9 PR-2)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from kosha.contradiction.detect import (
    ContradictionVerdict,
    GenerationContradictionJudge,
    LexicalContradictionJudge,
    build_contradiction_prompt,
    detect_conflict,
    find_conflict,
    parse_verdict,
    structured_diff,
)
from kosha.merge.claims import make_claim
from kosha.providers.base import Generation, Usage

_T0 = datetime(2026, 1, 1, tzinfo=UTC)

_RETURNS_30 = "Standard returns are accepted within 30 days of delivery."
_RETURNS_60 = "Standard returns are accepted within 60 days of delivery."
_GOLD_FREE = "Gold members receive free return shipping."
_GOLD_NO_FREE = "Gold members receive no free return shipping."
_REFUNDS = "Refunds post to the original payment card after approval."


class _CannedGenerator:
    """A generation provider that returns a fixed answer (real protocol impl)."""

    def __init__(self, answer: str) -> None:
        self._answer = answer

    @property
    def name(self) -> str:
        return "canned"

    def generate(self, query: str, context: str) -> Generation:
        return Generation(text=self._answer, usage=Usage(prompt_tokens=1, completion_tokens=1))


def test_structured_diff_flags_numeric_divergence_on_shared_subject() -> None:
    signal = structured_diff(_RETURNS_30, _RETURNS_60)
    assert signal.numeric_conflict is True
    assert signal.identical is False
    assert signal.subject_overlap > 0.5


def test_structured_diff_flags_polarity_flip() -> None:
    signal = structured_diff(_GOLD_FREE, _GOLD_NO_FREE)
    assert signal.negation_conflict is True
    assert signal.numeric_conflict is False


def test_structured_diff_marks_identical_restatement() -> None:
    signal = structured_diff(_RETURNS_30, f"  {_RETURNS_30}  ")
    assert signal.identical is True


def test_lexical_judge_calls_numeric_conflict() -> None:
    judge = LexicalContradictionJudge()
    result = judge.judge(_RETURNS_30, _RETURNS_60, structured_diff(_RETURNS_30, _RETURNS_60))
    assert result.verdict is ContradictionVerdict.CONFLICT
    assert "value" in result.rationale


def test_lexical_judge_calls_polarity_conflict() -> None:
    judge = LexicalContradictionJudge()
    result = judge.judge(_GOLD_FREE, _GOLD_NO_FREE, structured_diff(_GOLD_FREE, _GOLD_NO_FREE))
    assert result.verdict is ContradictionVerdict.CONFLICT
    assert "polarity" in result.rationale


def test_lexical_judge_treats_restatement_as_compatible() -> None:
    judge = LexicalContradictionJudge()
    result = judge.judge(_RETURNS_30, _RETURNS_30, structured_diff(_RETURNS_30, _RETURNS_30))
    assert result.verdict is ContradictionVerdict.NONE
    assert "restatement" in result.rationale


def test_lexical_judge_treats_unrelated_addition_as_compatible() -> None:
    judge = LexicalContradictionJudge()
    result = judge.judge(_RETURNS_30, _REFUNDS, structured_diff(_RETURNS_30, _REFUNDS))
    assert result.verdict is ContradictionVerdict.NONE


def test_lexical_judge_misses_paraphrased_conflict_leaving_llm_headroom() -> None:
    # A value conflict expressed in words, not digits, with no negation cue:
    # the lexical signals do not fire, so the offline judge says compatible.
    spelled = "Standard returns are accepted within sixty days of delivery."
    judge = LexicalContradictionJudge()
    result = judge.judge(_RETURNS_30, spelled, structured_diff(_RETURNS_30, spelled))
    assert result.verdict is ContradictionVerdict.NONE


def test_lexical_judge_rejects_out_of_range_overlap() -> None:
    with pytest.raises(ValueError, match="overlap_min"):
        LexicalContradictionJudge(overlap_min=1.5)


def test_detect_conflict_reports_the_old_claim_id_and_score() -> None:
    old = make_claim(_RETURNS_30, "s1", _T0)
    report = detect_conflict(old, _RETURNS_60, judge=LexicalContradictionJudge())
    assert report.conflicting is True
    assert report.old_claim_id == old.claim_id
    assert report.new_statement == _RETURNS_60
    assert report.score > 0.0


def test_find_conflict_picks_the_conflicting_claim_among_many() -> None:
    claims = [
        make_claim(_GOLD_FREE, "s1", _T0),
        make_claim(_RETURNS_30, "s1", _T0),
        make_claim(_REFUNDS, "s1", _T0),
    ]
    report = find_conflict(claims, _RETURNS_60, judge=LexicalContradictionJudge())
    assert report.conflicting is True
    assert report.old_claim_id == claims[1].claim_id


def test_find_conflict_returns_none_for_a_compatible_addition() -> None:
    claims = [make_claim(_RETURNS_30, "s1", _T0), make_claim(_GOLD_FREE, "s1", _T0)]
    report = find_conflict(claims, _REFUNDS, judge=LexicalContradictionJudge())
    assert report.conflicting is False
    assert report.verdict is ContradictionVerdict.NONE


def test_find_conflict_with_no_claims_reports_nothing_to_compare() -> None:
    report = find_conflict([], _RETURNS_30, judge=LexicalContradictionJudge())
    assert report.conflicting is False
    assert report.old_claim_id is None


def test_parse_verdict_handles_no_conflict_without_false_positive() -> None:
    assert parse_verdict("no conflict") is ContradictionVerdict.NONE
    assert parse_verdict("compatible") is ContradictionVerdict.NONE
    assert parse_verdict("conflict") is ContradictionVerdict.CONFLICT
    assert parse_verdict("These contradict each other.") is ContradictionVerdict.CONFLICT


def test_parse_verdict_rejects_a_verdict_free_response() -> None:
    with pytest.raises(ValueError, match="no contradiction verdict"):
        parse_verdict("I am not sure")


def test_generation_judge_parses_the_model_verdict() -> None:
    judge = GenerationContradictionJudge(_CannedGenerator("conflict"))
    result = judge.judge(_RETURNS_30, _RETURNS_60, structured_diff(_RETURNS_30, _RETURNS_60))
    assert result.verdict is ContradictionVerdict.CONFLICT
    assert "conflict" in result.rationale


def test_generation_judge_catches_the_paraphrase_the_lexical_judge_missed() -> None:
    spelled = "Standard returns are accepted within sixty days of delivery."
    judge = GenerationContradictionJudge(_CannedGenerator("conflict"))
    result = judge.judge(_RETURNS_30, spelled, structured_diff(_RETURNS_30, spelled))
    assert result.verdict is ContradictionVerdict.CONFLICT


def test_contradiction_prompt_carries_both_claims_and_the_instruction() -> None:
    query, context = build_contradiction_prompt("PRIOR_TEXT", "NEW_TEXT")
    assert "conflict" in query.lower()
    assert "PRIOR_TEXT" in context
    assert "NEW_TEXT" in context


def test_contradiction_prompt_defaults_to_flagging_on_uncertainty() -> None:
    # Gate-0 v2 (M3): the strict "materially contradicts" framing let the judge
    # answer compatible on subtle regimes; the safety-preserving framing must
    # default to flagging a conflict when unsure, mirroring the safety-instructed
    # baseline it is measured against.
    query, _ = build_contradiction_prompt("PRIOR_TEXT", "NEW_TEXT")
    lowered = query.lower()
    assert "when unsure, flag conflict" in lowered
    assert "materially contradicts" not in lowered


def test_contradiction_prompt_names_the_subtle_conflict_regimes() -> None:
    # The prompt must name the regime shapes a strict framing missed (S2 report):
    # scope (partial), unit/time window (unit), state change (temporal), and
    # reworded meaning (adversarial paraphrase) — not just numeric/negation.
    query, _ = build_contradiction_prompt("PRIOR_TEXT", "NEW_TEXT")
    lowered = query.lower()
    assert "narrower or broader scope" in lowered
    assert "unit or time window" in lowered
    assert "state that has since changed" in lowered
    assert "reworded claim that shifts the meaning" in lowered
