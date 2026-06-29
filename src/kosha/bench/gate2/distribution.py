"""N-run distributions for the Gate-0 v2 re-test (spike S2).

Generation runs at the provider's default sampling temperature, so every quality
rate oscillates run-to-run (KOSHA_STRATEGIC_ANALYSIS §2.4: "the generation
provider uses default (non-deterministic) sampling"). A single run is therefore
not evidence; the Gate-0 v2 criterion reads each axis as a *distribution* over
``N`` runs and only counts a win that survives the non-determinism noise band.

This module is the pure aggregation half: it turns a list of per-run rates into a
:class:`Distribution` (median + interval) with no provider or I/O dependency, so
the criterion and its verdict are deterministic and fixture-testable.
"""

from __future__ import annotations

import statistics
from collections.abc import Callable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Distribution:
    """The empirical distribution of one rate measured over several runs.

    ``lo``/``hi`` are the observed extremes — the interval the rate ranged over
    across the runs. They define the non-determinism noise band the Gate-0 v2
    criterion must see a win clear (a win is real only when the loop's worst run
    still beats the prompt's best run; see :mod:`kosha.bench.gate2.criterion`).
    """

    values: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.values:
            raise ValueError("a distribution needs at least one run")

    @property
    def n(self) -> int:
        return len(self.values)

    @property
    def median(self) -> float:
        return statistics.median(self.values)

    @property
    def mean(self) -> float:
        return statistics.fmean(self.values)

    @property
    def lo(self) -> float:
        return min(self.values)

    @property
    def hi(self) -> float:
        return max(self.values)

    @property
    def spread(self) -> float:
        """Width of the observed interval — the run-to-run noise band."""
        return self.hi - self.lo


def aggregate(values: Sequence[float]) -> Distribution:
    """Collect per-run rates into a :class:`Distribution` (order-independent)."""
    return Distribution(tuple(values))


def run_distribution(measure: Callable[[], float], runs: int) -> Distribution:
    """Call ``measure`` ``runs`` times and aggregate the rates it returns."""
    if runs < 1:
        raise ValueError("runs must be >= 1")
    return aggregate([measure() for _ in range(runs)])
