"""Tests for the seed labels and the threshold-only dedup baseline."""

from __future__ import annotations

import json
from pathlib import Path

from kosha.bench import (
    evaluate_granularity,
    evaluate_threshold_only,
    load_dedup_pairs,
    load_granularity_labels,
)
from kosha.eval import load_contradict_cases, load_merge_cases, load_relate_cases
from kosha.providers import LexicalEmbeddingProvider

ROOT = Path(__file__).resolve().parents[2]
DEDUP = ROOT / "labels" / "dedup_seed.jsonl"
GRANULARITY = ROOT / "labels" / "granularity_seed.jsonl"
MERGE = ROOT / "labels" / "merge_seed.jsonl"
RELATE = ROOT / "labels" / "relate_seed.jsonl"
CONTRADICT = ROOT / "labels" / "contradict_seed.jsonl"
LABEL_FILES = (DEDUP, GRANULARITY, MERGE, RELATE, CONTRADICT)
REALWORLD_FILES = (
    ROOT / "evals" / "realworld" / "queries.jsonl",
    ROOT / "evals" / "realworld" / "maintenance.jsonl",
    ROOT / "evals" / "paper_s2v3" / "queries.jsonl",
    ROOT / "evals" / "paper_s2v3" / "maintenance.jsonl",
)


def _jsonl(path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parsed = json.loads(stripped)
        assert isinstance(parsed, dict), path
        records.append(parsed)
    return records


def _fingerprint(value: object) -> str:
    if isinstance(value, dict):
        return " ".join(_fingerprint(value[key]) for key in sorted(value))
    if isinstance(value, list):
        return " ".join(_fingerprint(item) for item in value)
    return " ".join(str(value).lower().split())


def test_label_corpus_has_m2_scale_and_all_suites_load() -> None:
    assert len(load_dedup_pairs(DEDUP)) == 160
    assert len(load_granularity_labels(GRANULARITY)) == 110

    assert len(load_merge_cases(MERGE)) == 80
    assert len(load_relate_cases(RELATE)) == 80
    assert len(load_contradict_cases(CONTRADICT)) == 156

    assert sum(len(_jsonl(path)) for path in LABEL_FILES) >= 550


def test_label_corpus_has_no_duplicate_records() -> None:
    fingerprints: dict[str, Path] = {}
    for path in LABEL_FILES:
        for record in _jsonl(path):
            fingerprint = _fingerprint(record)
            assert fingerprint not in fingerprints, (path, fingerprints.get(fingerprint))
            fingerprints[fingerprint] = path


def test_label_corpus_does_not_leak_held_out_realworld_rows() -> None:
    label_texts = {
        _fingerprint(record)
        for path in LABEL_FILES
        for record in _jsonl(path)
    }
    held_out_texts = {
        _fingerprint(record)
        for path in REALWORLD_FILES
        for record in _jsonl(path)
    }
    assert label_texts.isdisjoint(held_out_texts)


def test_dedup_seed_meets_minimum_and_schema() -> None:
    pairs = load_dedup_pairs(DEDUP)
    assert len(pairs) >= 20
    assert all(p.label in {"same", "different"} for p in pairs)
    assert all(p.band in {"clear", "ambiguous"} for p in pairs)
    assert any(p.band == "ambiguous" for p in pairs)


def test_contradict_seed_covers_every_subtle_regime() -> None:
    cases = load_contradict_cases(CONTRADICT)
    regimes = {case.regime for case in cases}
    # M3 acceptance: the label corpus must exercise all four subtle regimes the
    # S2 report diagnosed as the judge's blind spot, each with real headroom
    # (both conflict and none cases, so precision and recall are both measured).
    for regime in ("unit", "partial", "temporal", "adversarial"):
        assert regime in regimes, regime
        by_label = {case.label for case in cases if case.regime == regime}
        assert by_label == {"conflict", "none"}, (regime, by_label)


def test_threshold_only_leaves_an_unresolved_ambiguous_band() -> None:
    pairs = load_dedup_pairs(DEDUP)
    signal = evaluate_threshold_only(pairs, LexicalEmbeddingProvider())
    assert signal.pair_count == len(pairs)
    # The seed set is built so no single threshold separates it: the loop has headroom.
    assert signal.best_accuracy < 1.0
    assert signal.ambiguous_errors > 0


def test_threshold_only_is_deterministic() -> None:
    pairs = load_dedup_pairs(DEDUP)
    a = evaluate_threshold_only(pairs, LexicalEmbeddingProvider())
    b = evaluate_threshold_only(pairs, LexicalEmbeddingProvider())
    assert a == b


def test_granularity_lint_separates_atomic_from_overscoped() -> None:
    labels = load_granularity_labels(GRANULARITY)
    signal = evaluate_granularity(labels)
    assert signal.label_count == len(labels) >= 4
    # Authored against the M3 lint contract: overscoped flagged, atomic clean.
    assert signal.correct == signal.label_count
