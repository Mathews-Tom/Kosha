"""The regime-spanning, scaled held-out contradiction set (spike S2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from kosha.bench.gate2.contradictions import (
    SCALES,
    build_contradiction_set,
    load_contradictions,
    regimes_present,
    render_jsonl,
)
from kosha.bench.gate2.criterion import MIN_CONTRADICTIONS, REGIMES

ROOT = Path(__file__).resolve().parents[2]
COMMITTED = ROOT / "evals" / "realworld" / "contradictions_v2.jsonl"


def test_generated_set_is_powered_and_spans_regimes() -> None:
    cases = build_contradiction_set()
    assert len(cases) >= MIN_CONTRADICTIONS
    assert regimes_present(cases) == REGIMES
    assert set(case.scale for case in cases) == set(SCALES)


def test_committed_file_matches_the_generator() -> None:
    # Provenance: the committed held-out file is exactly what the generator emits.
    assert COMMITTED.read_text(encoding="utf-8") == render_jsonl(build_contradiction_set())


def test_loader_round_trips_the_committed_set() -> None:
    cases = load_contradictions(COMMITTED)
    assert len(cases) >= MIN_CONTRADICTIONS
    assert regimes_present(cases) == REGIMES


def test_scale_fields_are_consistent() -> None:
    for case in load_contradictions(COMMITTED):
        if case.scale == "deep_history":
            assert 10 <= case.depth <= 50
            assert case.filler == 0
        elif case.scale == "buried_body":
            assert case.filler > 0
            assert case.depth == 0
        else:
            assert case.scale == "clean"
            assert case.depth == 0 and case.filler == 0


def test_prior_and_new_differ_per_case() -> None:
    for case in load_contradictions(COMMITTED):
        assert case.prior != case.new
        assert case.subject in case.prior
        assert case.subject in case.new


def test_loader_rejects_a_non_integer_depth(tmp_path: Path) -> None:
    bad = tmp_path / "bad.jsonl"
    bad.write_text(
        '{"id":"x","regime":"numeric","scale":"clean","subject":"s",'
        '"prior":"a","new":"b","depth":"deep","filler":0}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="depth"):
        load_contradictions(bad)


def test_loader_rejects_empty_file(tmp_path: Path) -> None:
    empty = tmp_path / "empty.jsonl"
    empty.write_text("\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no contradiction cases"):
        load_contradictions(empty)
