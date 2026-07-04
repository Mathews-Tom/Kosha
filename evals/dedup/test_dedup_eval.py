"""Dedup eval suite: precision/recall on labeled pairs + repeated-ingest duplicate rate."""

from __future__ import annotations

from pathlib import Path

from kosha.bench import load_dedup_pairs
from kosha.dedup import LexicalAdjudicator
from kosha.eval import evaluate_dedup, evaluate_duplicate_rate
from kosha.okf import load_bundle
from kosha.providers import LexicalEmbeddingProvider
from kosha.telemetry import InMemoryTelemetrySink

ROOT = Path(__file__).resolve().parents[2]
DEDUP = ROOT / "labels" / "dedup_seed.jsonl"
NORTHWIND = ROOT / "bundles" / "northwind"


def _report() -> object:
    return evaluate_dedup(
        load_dedup_pairs(DEDUP), LexicalEmbeddingProvider(), adjudicator=LexicalAdjudicator()
    )


def test_dedup_eval_reports_precision_and_recall() -> None:
    pairs = load_dedup_pairs(DEDUP)
    report = evaluate_dedup(pairs, LexicalEmbeddingProvider(), adjudicator=LexicalAdjudicator())
    assert report.pair_count == len(pairs)
    assert 0.0 <= report.precision <= 1.0
    assert 0.0 <= report.recall <= 1.0
    assert report.true_positive + report.false_positive + report.false_negative + (
        report.true_negative
    ) == len(pairs)


def test_resolver_nails_the_clear_band() -> None:
    # On clearly-same/clearly-different pairs the two-threshold + lexical adjudicator
    # path is precise; the ambiguous band is the documented LLM headroom.
    clear = [p for p in load_dedup_pairs(DEDUP) if p.band == "clear"]
    report = evaluate_dedup(clear, LexicalEmbeddingProvider(), adjudicator=LexicalAdjudicator())
    assert report.precision == 1.0
    assert report.accuracy >= 0.9


def test_ambiguous_band_leaves_headroom_for_a_real_model() -> None:
    # The seed is built so lexical signals cannot fully separate it; offline
    # accuracy stays below 1.0, which is exactly the gap a real LLM closes.
    report = evaluate_dedup(
        load_dedup_pairs(DEDUP), LexicalEmbeddingProvider(), adjudicator=LexicalAdjudicator()
    )
    assert report.accuracy < 1.0


def test_dedup_eval_is_deterministic() -> None:
    a = evaluate_dedup(
        load_dedup_pairs(DEDUP), LexicalEmbeddingProvider(), adjudicator=LexicalAdjudicator()
    )
    b = evaluate_dedup(
        load_dedup_pairs(DEDUP), LexicalEmbeddingProvider(), adjudicator=LexicalAdjudicator()
    )
    assert a == b


def test_dedup_eval_emits_decision_telemetry() -> None:
    pairs = load_dedup_pairs(DEDUP)[:4]
    sink = InMemoryTelemetrySink()

    report = evaluate_dedup(
        pairs,
        LexicalEmbeddingProvider(),
        adjudicator=LexicalAdjudicator(),
        telemetry_sink=sink,
    )

    assert report.pair_count == len(pairs)
    assert len(sink.records) == len(pairs)
    assert {record["kind"] for record in sink.records} == {"decision"}
    assert all("outcome" in record and "confidence" in record for record in sink.records)


def test_repeated_ingest_has_zero_duplicate_rate() -> None:
    bundle = load_bundle(NORTHWIND)
    report = evaluate_duplicate_rate(
        bundle, LexicalEmbeddingProvider(), adjudicator=LexicalAdjudicator()
    )
    assert report.concept_count == len(bundle.concepts) == 12
    assert report.created == 0
    assert report.updated == report.concept_count
    assert report.duplicate_rate == 0.0
