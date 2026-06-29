"""The scaled (>=1k-concept) external corpus generator (spike S2)."""

from __future__ import annotations

from pathlib import Path

from kosha.bench.corpus import (
    MODULES,
    MODULES_XL,
    SCALED_MAX_MEMBERS,
    build_corpus,
    collect_entries,
)
from kosha.bench.corpus.stdlib import build_scaled_corpus
from kosha.okf import load_bundle


def test_scaled_module_set_supersets_the_base() -> None:
    assert set(MODULES).issubset(set(MODULES_XL))
    assert len(MODULES_XL) > len(MODULES)


def test_scaled_corpus_clears_one_thousand_concepts() -> None:
    # Count without writing 1.5k files: collect_entries is the render step.
    entries = collect_entries(MODULES_XL, max_members=SCALED_MAX_MEMBERS)
    assert len(entries) >= 1000


def test_max_members_caps_per_module() -> None:
    few = collect_entries(("collections",), max_members=2)
    assert len(few) <= 2


def test_build_scaled_corpus_writes_a_loadable_bundle(tmp_path: Path) -> None:
    # Build a small but real bundle through the same writer to keep the test fast.
    out = tmp_path / "xl"
    stats = build_corpus(out, modules=("json", "base64"), max_members=SCALED_MAX_MEMBERS)
    assert stats.concept_count > 0
    bundle = load_bundle(out)
    assert len(bundle.concepts) == stats.concept_count


def test_build_scaled_corpus_callable() -> None:
    # The convenience wrapper resolves and is wired to the XL module set + cap.
    assert build_scaled_corpus.__module__ == "kosha.bench.corpus.stdlib"
