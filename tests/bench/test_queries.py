"""Tests that the benchmark ground truth references real corpus concepts."""

from __future__ import annotations

from pathlib import Path

from kosha.bench import NORTHWIND_QUERIES
from kosha.okf import load_bundle

NORTHWIND = Path(__file__).resolve().parents[2] / "bundles" / "northwind"


def test_query_ids_are_unique() -> None:
    ids = [q.id for q in NORTHWIND_QUERIES]
    assert len(ids) == len(set(ids))
    assert ids


def test_every_required_concept_exists_in_the_corpus() -> None:
    bundle = load_bundle(NORTHWIND)
    for query in NORTHWIND_QUERIES:
        assert query.required_concepts, f"{query.id} has no required concepts"
        for concept_id in query.required_concepts:
            assert concept_id in bundle.concepts, f"{query.id} -> missing {concept_id}"
