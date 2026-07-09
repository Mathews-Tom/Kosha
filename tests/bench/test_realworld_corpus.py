"""Deterministic guards for the M13 external corpus and held-out label sets.

These cover the offline, network-free parts of the real-model suite: the
committed ``bundles/pydoc-stdlib`` corpus loads and is OKF-conformant, the
generator is deterministic and collision-free, and every held-out query and
maintenance case references a concept that actually exists in the corpus.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kosha.bench.corpus import build_corpus, collect_entries
from kosha.bench.realworld import load_maintenance, load_queries
from kosha.okf import load_bundle
from kosha.validate import validate_bundle

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "bundles" / "pydoc-stdlib"
QUERIES = ROOT / "evals" / "realworld" / "queries.jsonl"
MAINTENANCE = ROOT / "evals" / "realworld" / "maintenance.jsonl"
S2V3_MANIFEST = ROOT / "bundles" / "paper-s2v3-corpus" / "MANIFEST.md"
S2V3_CORPUS = ROOT / "bundles" / "paper-s2v3-corpus"
S2V3_QUERIES = ROOT / "evals" / "paper_s2v3" / "queries.jsonl"
S2V3_MAINTENANCE = ROOT / "evals" / "paper_s2v3" / "maintenance.jsonl"


def test_s2v3_corpus_manifest_exists_and_is_valid() -> None:
    assert S2V3_MANIFEST.exists()
    text = S2V3_MANIFEST.read_text("utf-8")
    assert "**Domain:**" in text
    assert "**Source:**" in text
    assert "**License:**" in text
    assert "**Privacy:**" in text
    assert "Exclusion Criteria" in text
    assert "non-Python" in text


def test_corpus_is_external_scale() -> None:
    bundle = load_bundle(CORPUS)
    # M13 requires an external 500-2,000-concept corpus.
    assert 500 <= len(bundle.concepts) <= 2000


def test_corpus_is_okf_conformant() -> None:
    report = validate_bundle(CORPUS)
    errors = [f for f in report.findings if f.severity.value == "error"]
    assert errors == [], errors
    assert report.ok


def test_corpus_has_traversable_links() -> None:
    bundle = load_bundle(CORPUS)
    linked = sum(1 for concept in bundle.concepts.values() if concept.out_links)
    # The hybrid strategy traverses out-links; the corpus must not be flat islands.
    assert linked >= 0.9 * len(bundle.concepts)
    # Every out-link must resolve to a concept that exists (no dangling traversal).
    for concept in bundle.concepts.values():
        for target in concept.out_links:
            assert target in bundle.concepts, (concept.concept_id, target)


@pytest.mark.parametrize(
    "corpus_path,queries_path",
    [
        (CORPUS, QUERIES),
        (S2V3_CORPUS, S2V3_QUERIES),
    ],
)
def test_held_out_queries_reference_real_concepts(corpus_path: Path, queries_path: Path) -> None:
    if not corpus_path.exists() or not queries_path.exists():
        pytest.skip(f"{corpus_path} not ready")
    bundle = load_bundle(corpus_path)
    queries = load_queries(queries_path)
    assert len(queries) >= 1
    for query in queries:
        assert query.required_concepts
        for concept_id in query.required_concepts:
            assert concept_id in bundle.concepts, (query.id, concept_id)


@pytest.mark.parametrize(
    "corpus_path,maintenance_path",
    [
        (CORPUS, MAINTENANCE),
        (S2V3_CORPUS, S2V3_MAINTENANCE),
    ],
)
def test_held_out_maintenance_references_real_concepts(
    corpus_path: Path, maintenance_path: Path
) -> None:
    if not corpus_path.exists() or not maintenance_path.exists():
        pytest.skip(f"{corpus_path} not ready")
    bundle = load_bundle(corpus_path)
    cases = load_maintenance(maintenance_path)
    assert len(cases) >= 1
    for case in cases:
        if case.target is not None:
            assert case.target in bundle.concepts, (case.id, case.target)


@pytest.mark.parametrize(
    "maintenance_path",
    [
        MAINTENANCE,
        S2V3_MAINTENANCE,
    ],
)
def test_maintenance_labels_are_self_consistent(maintenance_path: Path) -> None:
    if not maintenance_path.exists():
        pytest.skip(f"{maintenance_path} not ready")
    cases = load_maintenance(maintenance_path)
    kinds = {case.kind for case in cases}
    assert kinds.issubset({"duplicate", "novel", "contradiction"})
    for case in cases:
        if case.kind == "novel":
            assert case.expected_action == "CREATE"
            assert case.target is None
        else:
            assert case.expected_action == "UPDATE"
            assert case.target is not None


def test_generator_is_deterministic() -> None:
    first = collect_entries()
    second = collect_entries()
    assert first == second


def test_generator_ids_are_well_formed() -> None:
    entries = collect_entries()
    ids = [entry.concept_id for entry in entries]
    # No id renders to a reserved bundle file, and none collide case-insensitively.
    assert all(cid.rsplit("/", 1)[-1] not in {"index", "log"} for cid in ids)
    assert len({cid.casefold() for cid in ids}) == len(ids)


def test_build_round_trips_every_entry(tmp_path: Path) -> None:
    stats = build_corpus(tmp_path)
    bundle = load_bundle(tmp_path)
    # No entry is silently lost to a path collision on either filesystem flavor.
    assert len(bundle.concepts) == stats.concept_count


def test_cli_bench_corpus_regenerates(tmp_path: Path) -> None:
    from kosha.cli import main

    out = tmp_path / "corpus"
    assert main(["bench", "corpus", "--out", str(out)]) == 0
    bundle = load_bundle(out)
    assert 500 <= len(bundle.concepts) <= 2000
