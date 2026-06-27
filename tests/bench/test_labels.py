"""Tests for the seed labels and the threshold-only dedup baseline."""

from __future__ import annotations

from pathlib import Path

from kosha.bench import (
    evaluate_granularity,
    evaluate_threshold_only,
    load_dedup_pairs,
    load_granularity_labels,
)
from kosha.providers import LexicalEmbeddingProvider

ROOT = Path(__file__).resolve().parents[2]
DEDUP = ROOT / "labels" / "dedup_seed.jsonl"
GRANULARITY = ROOT / "labels" / "granularity_seed.jsonl"


def test_dedup_seed_meets_minimum_and_schema() -> None:
    pairs = load_dedup_pairs(DEDUP)
    assert len(pairs) >= 20
    assert all(p.label in {"same", "different"} for p in pairs)
    assert all(p.band in {"clear", "ambiguous"} for p in pairs)
    assert any(p.band == "ambiguous" for p in pairs)


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
