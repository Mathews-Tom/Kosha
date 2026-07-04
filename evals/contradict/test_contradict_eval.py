"""Contradict eval suite: conflict-detection quality over the seed cases."""

from __future__ import annotations

from pathlib import Path

from kosha.contradiction import LexicalContradictionJudge
from kosha.eval import evaluate_contradict, evaluate_contradict_by_regime, load_contradict_cases

ROOT = Path(__file__).resolve().parents[2]
CONTRADICT = ROOT / "labels" / "contradict_seed.jsonl"


def test_contradict_eval_reports_a_score() -> None:
    cases = load_contradict_cases(CONTRADICT)
    report = evaluate_contradict(cases, LexicalContradictionJudge())
    assert report.case_count == len(cases)
    assert 0.0 <= report.precision <= 1.0
    assert 0.0 <= report.recall <= 1.0
    assert 0.0 <= report.f1 <= 1.0


def test_lexical_judge_nails_the_clear_band() -> None:
    # Numeric/polarity divergence on a shared subject vs restatement/addition:
    # the offline judge classifies the clear band perfectly.
    clear = [c for c in load_contradict_cases(CONTRADICT) if c.band == "clear"]
    report = evaluate_contradict(clear, LexicalContradictionJudge())
    assert report.precision == 1.0
    assert report.recall == 1.0
    assert report.accuracy == 1.0


def test_ambiguous_band_leaves_headroom_for_a_real_model() -> None:
    # Paraphrased conflicts (spelled-out values, week/month, narrowed scope) carry
    # no numeric or negation cue, so the lexical judge misses them — recall drops
    # below 1.0, the documented headroom a real model closes.
    report = evaluate_contradict(load_contradict_cases(CONTRADICT), LexicalContradictionJudge())
    assert report.recall < 1.0
    # It does not over-flag: paraphrased restatements stay compatible.
    assert report.precision == 1.0


def test_contradict_eval_is_deterministic() -> None:
    a = evaluate_contradict(load_contradict_cases(CONTRADICT), LexicalContradictionJudge())
    b = evaluate_contradict(load_contradict_cases(CONTRADICT), LexicalContradictionJudge())
    assert a == b


def test_lexical_judge_leaves_headroom_on_every_subtle_regime() -> None:
    # This is the headroom the S2 report diagnosed: the offline judge misses most
    # of each subtle regime (no numeric/negation cue survives lexically for most
    # cases), which is exactly the gap the safety-preserving
    # GenerationContradictionJudge prompt is measured against in the
    # real-provider Gate-0 v2 re-run.
    by_regime = evaluate_contradict_by_regime(
        load_contradict_cases(CONTRADICT), LexicalContradictionJudge()
    )
    for regime in ("unit", "partial", "temporal", "adversarial"):
        assert by_regime[regime].recall < 1.0, regime


def test_regime_breakdown_covers_every_case_exactly_once() -> None:
    cases = load_contradict_cases(CONTRADICT)
    by_regime = evaluate_contradict_by_regime(cases, LexicalContradictionJudge())
    assert sum(report.case_count for report in by_regime.values()) == len(cases)
