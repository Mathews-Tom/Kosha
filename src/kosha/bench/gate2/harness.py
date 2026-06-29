"""The multi-run, multi-model Gate-0 v2 harness (spike S2).

:func:`run_gate2` iterates the provider matrix, runs a per-cell measurement ``N``
times to capture the default-sampling noise, and aggregates each run into the
:class:`~kosha.bench.gate2.criterion.Gate2Report` whose verdict is fixed by the
pre-registered bar. The measurement itself is injected as a callable so the
harness stays free of held-out-set and detector concerns (those are wired by the
runner) and is exercisable with deterministic fixtures.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from kosha.bench.gate2.criterion import (
    AxisDistribution,
    CellResult,
    Gate2Criterion,
    Gate2Report,
)
from kosha.bench.gate2.distribution import aggregate
from kosha.providers.base import EmbeddingProvider, GenerationProvider
from kosha.providers.matrix import ProviderMatrix


@dataclass(frozen=True)
class AxisSample:
    """One run's loop-vs-prompt rate on a single quality axis."""

    axis: str
    loop: float
    prompt: float


@dataclass(frozen=True)
class CellSample:
    """One run's measurement for one provider cell."""

    axes: tuple[AxisSample, ...]
    loop_silent_overwrites: int
    contradictions: int
    regimes: tuple[str, ...]


# Measure one run for a provider cell. Injected by the runner (real held-out
# scoring) or a fixture (deterministic tests).
CellMeasure = Callable[[EmbeddingProvider, GenerationProvider], CellSample]
ProgressFn = Callable[[str], None]


def run_gate2(
    matrix: ProviderMatrix,
    measure: CellMeasure,
    *,
    criterion: Gate2Criterion | None = None,
    runs: int,
    audit_verified: bool | None = None,
    progress: ProgressFn | None = None,
) -> Gate2Report:
    """Run ``measure`` ``runs`` times per matrix cell and build the verdict report."""
    if runs < 1:
        raise ValueError("runs must be >= 1")
    bar = criterion or Gate2Criterion.preregistered()
    log = progress or (lambda _message: None)
    cells: list[CellResult] = []
    for embedding_label, embedding in matrix.embeddings:
        for generation_label, generation in matrix.generations:
            samples: list[CellSample] = []
            for run in range(runs):
                log(f"cell {embedding_label} x {generation_label}: run {run + 1}/{runs}")
                samples.append(measure(embedding, generation))
            cells.append(aggregate_cell(embedding_label, generation_label, samples))
    return Gate2Report(
        criterion=bar,
        cells=tuple(cells),
        embeddings=matrix.embedding_labels,
        generations=matrix.generation_labels,
        runs=runs,
        audit_verified=audit_verified,
    )


def aggregate_cell(
    embedding_label: str, generation_label: str, samples: Sequence[CellSample]
) -> CellResult:
    """Aggregate one cell's per-run samples into a :class:`CellResult`."""
    if not samples:
        raise ValueError("a cell needs at least one run")
    axis_names = [axis.axis for axis in samples[0].axes]
    for sample in samples:
        if [axis.axis for axis in sample.axes] != axis_names:
            raise ValueError("every run of a cell must report the same axes in order")
    axes = tuple(
        AxisDistribution(
            axis=name,
            loop=aggregate([_axis(sample, name).loop for sample in samples]),
            prompt=aggregate([_axis(sample, name).prompt for sample in samples]),
        )
        for name in axis_names
    )
    return CellResult(
        embedding_label=embedding_label,
        generation_label=generation_label,
        axes=axes,
        loop_silent_overwrites=sum(sample.loop_silent_overwrites for sample in samples),
        contradictions=min(sample.contradictions for sample in samples),
        regimes=samples[0].regimes,
    )


def _axis(sample: CellSample, name: str) -> AxisSample:
    for axis in sample.axes:
        if axis.axis == name:
            return axis
    raise KeyError(name)
