"""Relate eval suite: cross-link discovery quality over the seed cases (M8 PR-4)."""

from __future__ import annotations

from pathlib import Path

from kosha.cli import main
from kosha.eval import evaluate_relate, load_relate_cases
from kosha.link import LexicalRelator

ROOT = Path(__file__).resolve().parents[2]
RELATE = ROOT / "labels" / "relate_seed.jsonl"


def test_relate_eval_reports_scores() -> None:
    cases = load_relate_cases(RELATE)
    report = evaluate_relate(cases, LexicalRelator())
    assert report.case_count == len(cases)
    assert 0.0 <= report.precision <= 1.0
    assert 0.0 <= report.recall <= 1.0
    assert 0.0 <= report.f1 <= 1.0


def test_relator_recovers_the_clear_band() -> None:
    # Pairs that share a tag and vocabulary are recovered offline.
    clear = [case for case in load_relate_cases(RELATE) if case.band == "clear"]
    report = evaluate_relate(clear, LexicalRelator())
    assert report.recall == 1.0


def test_ambiguous_band_leaves_headroom_for_a_real_model() -> None:
    # A synonym-swapped, untagged relation defeats lexical overlap, so full-set
    # recall stays below 1.0 — the headroom a GenerationRelator closes.
    report = evaluate_relate(load_relate_cases(RELATE), LexicalRelator())
    assert report.recall < 1.0


def test_relate_eval_is_deterministic() -> None:
    a = evaluate_relate(load_relate_cases(RELATE), LexicalRelator())
    b = evaluate_relate(load_relate_cases(RELATE), LexicalRelator())
    assert a == b


def test_relate_eval_cli_runs() -> None:
    assert main(["eval", "relate"]) == 0
