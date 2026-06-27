"""Extractor eval suite: score boundary recovery against the seed labels."""

from __future__ import annotations

from pathlib import Path

from kosha.bench import load_granularity_labels
from kosha.eval import evaluate_extractor
from kosha.providers import ExtractiveGenerationProvider

ROOT = Path(__file__).resolve().parents[2]
GRANULARITY = ROOT / "labels" / "granularity_seed.jsonl"


def test_extractor_eval_reports_a_score() -> None:
    labels = load_granularity_labels(GRANULARITY)
    report = evaluate_extractor(labels, ExtractiveGenerationProvider())
    assert report.label_count == len(labels) >= 4
    assert 0.0 <= report.score <= 1.0


def test_extractor_recovers_seed_boundaries() -> None:
    labels = load_granularity_labels(GRANULARITY)
    report = evaluate_extractor(labels, ExtractiveGenerationProvider())
    # The heading-segmenting extractor matches every labeled granularity class:
    # atomic -> one draft, overscoped -> many.
    assert report.correct == report.label_count
    assert any(c.expected_atomic for c in report.cases)
    assert any(not c.expected_atomic for c in report.cases)


def test_extractor_eval_is_deterministic() -> None:
    labels = load_granularity_labels(GRANULARITY)
    first = evaluate_extractor(labels, ExtractiveGenerationProvider())
    second = evaluate_extractor(labels, ExtractiveGenerationProvider())
    assert first == second
