"""The multi-run, multi-model Gate-0 v2 harness (spike S2).

These cover the harness's two jobs: fold N runs of a per-cell measurement into a
distribution, and iterate the provider matrix into a verdict report. The
measurement is a deterministic fixture so the aggregation, not a model, is what
is under test.
"""

from __future__ import annotations

import pytest

from kosha.bench.gate2.harness import AxisSample, CellSample, aggregate_cell, run_gate2
from kosha.providers.base import EmbeddingProvider, GenerationProvider
from kosha.providers.extractive import ExtractiveGenerationProvider
from kosha.providers.lexical import LexicalEmbeddingProvider
from kosha.providers.matrix import ProviderMatrix


def _sample(loop: float, prompt: float, *, overwrites: int = 0, n: int = 100) -> CellSample:
    return CellSample(
        axes=(AxisSample("safety_rate", loop, prompt),),
        loop_silent_overwrites=overwrites,
        contradictions=n,
        regimes=("numeric", "negation"),
    )


def test_aggregate_cell_builds_axis_distributions() -> None:
    samples = [_sample(0.9, 0.6), _sample(0.95, 0.62), _sample(0.92, 0.58)]
    cell = aggregate_cell("bge-m3", "gpt-4o-mini", samples)
    axis = cell.axis("safety_rate")
    assert axis is not None
    assert axis.loop.median == pytest.approx(0.92)
    assert axis.prompt.median == pytest.approx(0.6)
    assert cell.contradictions == 100
    assert cell.regimes == ("numeric", "negation")


def test_aggregate_cell_sums_silent_overwrites_across_runs() -> None:
    samples = [_sample(0.9, 0.6), _sample(0.9, 0.6, overwrites=1)]
    cell = aggregate_cell("bge-m3", "gpt-4o-mini", samples)
    assert cell.loop_silent_overwrites == 1


def test_aggregate_cell_rejects_inconsistent_axes() -> None:
    a = _sample(0.9, 0.6)
    b = CellSample(
        axes=(AxisSample("detection_recall", 0.9, 0.6),),
        loop_silent_overwrites=0,
        contradictions=100,
        regimes=(),
    )
    with pytest.raises(ValueError, match="same axes"):
        aggregate_cell("bge-m3", "gpt-4o-mini", [a, b])


def test_aggregate_cell_needs_a_run() -> None:
    with pytest.raises(ValueError, match="at least one run"):
        aggregate_cell("bge-m3", "gpt-4o-mini", [])


def test_run_gate2_iterates_the_matrix() -> None:
    matrix = ProviderMatrix(
        embeddings=(("bge-m3", LexicalEmbeddingProvider()), ("nomic", LexicalEmbeddingProvider())),
        generations=(
            ("gpt-4o-mini", ExtractiveGenerationProvider()),
            ("gemma4", ExtractiveGenerationProvider()),
        ),
    )
    calls: list[tuple[int, int]] = []

    def measure(_embed: EmbeddingProvider, _gen: GenerationProvider) -> CellSample:
        calls.append((id(_embed), id(_gen)))
        return _sample(0.95, 0.6)

    report = run_gate2(matrix, measure, runs=3)
    assert len(report.cells) == 4
    assert report.runs == 3
    assert len(calls) == 12  # 4 cells x 3 runs
    assert report.embeddings == ("bge-m3", "nomic")
    assert report.generations == ("gpt-4o-mini", "gemma4")


def test_run_gate2_rejects_zero_runs() -> None:
    matrix = ProviderMatrix(
        embeddings=(("e", LexicalEmbeddingProvider()),),
        generations=(("g", ExtractiveGenerationProvider()),),
    )
    with pytest.raises(ValueError, match="runs must be"):
        run_gate2(matrix, lambda _e, _g: _sample(0.9, 0.6), runs=0)


def test_build_gate2_measure_runs_offline() -> None:
    """The runner-bound measure produces a safety_rate sample on local providers."""
    from pathlib import Path

    from kosha.bench.realworld import RealworldConfig, build_gate2_measure

    root = Path(__file__).resolve().parents[2]
    config = RealworldConfig(
        corpus=root / "bundles" / "pydoc-stdlib",
        queries=root / "evals" / "realworld" / "queries.jsonl",
        maintenance=root / "evals" / "realworld" / "maintenance.jsonl",
        guidance=root / "consumer" / "AGENTS.fragment.md",
        candidate_k=4,
    )
    measure = build_gate2_measure(config)
    sample = measure(LexicalEmbeddingProvider(), ExtractiveGenerationProvider())
    axes = {axis.axis for axis in sample.axes}
    assert "safety_rate" in axes
    assert sample.contradictions >= 1
    assert sample.loop_silent_overwrites == 0
