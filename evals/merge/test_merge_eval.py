"""Merge eval suite: claim-targeting accuracy over the seed cases."""

from __future__ import annotations

from pathlib import Path

from kosha.eval import evaluate_merge, load_merge_cases
from kosha.merge import LexicalClaimTargeter

ROOT = Path(__file__).resolve().parents[2]
MERGE = ROOT / "labels" / "merge_seed.jsonl"


def test_merge_eval_reports_a_score() -> None:
    cases = load_merge_cases(MERGE)
    report = evaluate_merge(cases, LexicalClaimTargeter())
    assert report.case_count == len(cases)
    assert 0.0 <= report.score <= 1.0
    assert report.correct == sum(1 for case in report.cases if case.correct)


def test_targeter_nails_the_clear_band() -> None:
    # Near-verbatim revisions overlap their claim lexically; the offline targeter
    # resolves the clear band perfectly.
    clear = [c for c in load_merge_cases(MERGE) if c.band == "clear"]
    report = evaluate_merge(clear, LexicalClaimTargeter())
    assert report.score == 1.0


def test_ambiguous_band_leaves_headroom_for_a_real_model() -> None:
    # A paraphrase whose wording diverges from the claim it revises defeats the
    # lexical targeter, so full-set accuracy stays below 1.0 — the LLM headroom.
    report = evaluate_merge(load_merge_cases(MERGE), LexicalClaimTargeter())
    assert report.score < 1.0


def test_merge_eval_is_deterministic() -> None:
    a = evaluate_merge(load_merge_cases(MERGE), LexicalClaimTargeter())
    b = evaluate_merge(load_merge_cases(MERGE), LexicalClaimTargeter())
    assert a == b
