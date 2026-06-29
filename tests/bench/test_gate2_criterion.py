"""The pre-registered Gate-0 v2 criterion and verdict (spike S2).

These fixtures pin the bar's behavior: a GO needs a quality margin cleared with
the non-determinism noise band excluded, on every provider cell, with the matrix,
sample, runs, and regimes all powered and zero silent overwrites. Each test holds
exactly one of those conditions back to prove it is load-bearing.
"""

from __future__ import annotations

import pytest

from kosha.bench.gate2.criterion import (
    MIN_CONTRADICTIONS,
    QUALITY_MARGIN,
    AxisDistribution,
    CellResult,
    Gate2Criterion,
    Gate2Report,
)
from kosha.bench.gate2.distribution import Distribution, aggregate

CRITERION = Gate2Criterion.preregistered()
REGIMES = CRITERION.regimes


def _axis(name: str, loop: list[float], prompt: list[float]) -> AxisDistribution:
    return AxisDistribution(name, aggregate(loop), aggregate(prompt))


def _cell(
    embedding: str,
    generation: str,
    *,
    loop: list[float],
    prompt: list[float],
    axis: str = "safety_rate",
    overwrites: int = 0,
    contradictions: int = MIN_CONTRADICTIONS,
    regimes: tuple[str, ...] = REGIMES,
) -> CellResult:
    return CellResult(
        embedding_label=embedding,
        generation_label=generation,
        axes=(_axis(axis, loop, prompt),),
        loop_silent_overwrites=overwrites,
        contradictions=contradictions,
        regimes=regimes,
    )


def _report(cells: tuple[CellResult, ...], *, runs: int = CRITERION.min_runs) -> Gate2Report:
    embeddings = tuple(sorted({cell.embedding_label for cell in cells}))
    generations = tuple(sorted({cell.generation_label for cell in cells}))
    return Gate2Report(
        criterion=CRITERION,
        cells=cells,
        embeddings=embeddings,
        generations=generations,
        runs=runs,
    )


def _powered_go_cells() -> tuple[CellResult, ...]:
    """A 2x2 matrix where the loop clears the margin and noise band on every cell."""
    return tuple(
        _cell(embed, gen, loop=[0.95, 0.97, 0.96], prompt=[0.60, 0.62, 0.58])
        for embed in ("bge-m3", "nomic")
        for gen in ("gpt-4o-mini", "gemma4")
    )


def test_distribution_summary_stats() -> None:
    dist = Distribution((0.6, 0.8, 0.7))
    assert dist.n == 3
    assert dist.median == pytest.approx(0.7)
    assert dist.lo == pytest.approx(0.6)
    assert dist.hi == pytest.approx(0.8)
    assert dist.spread == pytest.approx(0.2)


def test_empty_distribution_rejected() -> None:
    with pytest.raises(ValueError, match="at least one run"):
        Distribution(())


def test_axis_cleared_requires_margin_and_noise_band() -> None:
    clear = _axis("safety_rate", [0.95, 0.96], [0.60, 0.62])
    assert clear.median_delta >= QUALITY_MARGIN
    assert clear.noise_band_excluded
    assert clear.cleared(QUALITY_MARGIN)


def test_axis_inside_noise_band_not_cleared() -> None:
    # Median gap clears the margin, but the loop's worst run (0.70) does not beat
    # the prompt's best run (0.74): the win is inside the non-determinism band.
    overlap = _axis("safety_rate", [0.70, 0.92], [0.40, 0.74])
    assert overlap.median_delta >= QUALITY_MARGIN
    assert not overlap.noise_band_excluded
    assert not overlap.cleared(QUALITY_MARGIN)


def test_axis_below_margin_not_cleared() -> None:
    thin = _axis("safety_rate", [0.70, 0.71], [0.62, 0.63])
    assert thin.noise_band_excluded
    assert thin.median_delta < QUALITY_MARGIN
    assert not thin.cleared(QUALITY_MARGIN)


def test_powered_clearing_matrix_is_go() -> None:
    report = _report(_powered_go_cells())
    assert report.powered
    assert report.no_silent_overwrites
    assert report.carrying_axis == "safety_rate"
    assert report.verdict == "GO"
    assert report.authorizes_m14


def test_underpowered_matrix_cannot_go() -> None:
    # One embedding, one generation: the win cannot generalize across the matrix.
    cell = _cell("bge-m3", "gpt-4o-mini", loop=[0.95, 0.97, 0.96], prompt=[0.6, 0.62, 0.58])
    report = _report((cell,))
    assert not report.matrix_powered
    assert report.verdict == "NO-GO"
    assert not report.authorizes_m14


def test_underpowered_sample_cannot_go() -> None:
    cells = tuple(
        _cell(embed, gen, loop=[0.95, 0.97, 0.96], prompt=[0.6, 0.62, 0.58], contradictions=6)
        for embed in ("bge-m3", "nomic")
        for gen in ("gpt-4o-mini", "gemma4")
    )
    report = _report(cells)
    assert not report.sample_powered
    assert report.verdict == "NO-GO"


def test_underpowered_runs_cannot_go() -> None:
    report = _report(_powered_go_cells(), runs=1)
    assert not report.runs_powered
    assert report.verdict == "NO-GO"


def test_missing_regime_coverage_cannot_go() -> None:
    cells = tuple(
        _cell(embed, gen, loop=[0.95, 0.97, 0.96], prompt=[0.6, 0.62, 0.58], regimes=("numeric",))
        for embed in ("bge-m3", "nomic")
        for gen in ("gpt-4o-mini", "gemma4")
    )
    report = _report(cells)
    assert not report.regimes_powered
    assert report.verdict == "NO-GO"


def test_silent_overwrite_cannot_go() -> None:
    cells = list(_powered_go_cells())
    cells[1] = _cell(
        cells[1].embedding_label,
        cells[1].generation_label,
        loop=[0.95, 0.97, 0.96],
        prompt=[0.60, 0.62, 0.58],
        overwrites=1,
    )
    report = _report(tuple(cells))
    assert not report.no_silent_overwrites
    assert report.verdict == "NO-GO"


def test_win_on_one_cell_only_is_not_a_carrying_axis() -> None:
    # Clears on three cells but ties on the fourth: no axis cleared on EVERY cell.
    cells = list(_powered_go_cells())
    cells[3] = _cell(
        cells[3].embedding_label,
        cells[3].generation_label,
        loop=[0.64, 0.66, 0.65],
        prompt=[0.60, 0.62, 0.61],
    )
    report = _report(tuple(cells))
    assert report.powered
    assert report.carrying_axis is None
    assert report.verdict == "NO-GO"


def test_describe_states_the_bar() -> None:
    text = CRITERION.describe()
    assert "noise band" in text
    assert f">={MIN_CONTRADICTIONS}" in text
    assert "M14+ stays halted" in text
