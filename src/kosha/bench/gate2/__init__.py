"""Pre-registered Gate-0 v2 re-test (spike S2).

Gate-0 v2 re-opens the Gate-0 question after M13 tied on a tiny, clean held-out
set: *does the maintenance loop beat a good prompt on a buyer-relevant axis at
scale?* The bar — margin, sample size, regimes, provider matrix — is fixed in
:mod:`kosha.bench.gate2.criterion` BEFORE any measurement so the verdict cannot
be tuned to the result. :mod:`kosha.bench.gate2.distribution` holds the pure
N-run aggregation the criterion reads.
"""

from __future__ import annotations

from kosha.bench.gate2.criterion import (
    MIN_CONTRADICTIONS,
    MIN_EMBEDDINGS,
    MIN_GEN_MODELS,
    MIN_RUNS,
    QUALITY_AXES,
    QUALITY_MARGIN,
    REGIMES,
    AxisDistribution,
    CellResult,
    Gate2Criterion,
    Gate2Report,
)
from kosha.bench.gate2.distribution import Distribution, aggregate, run_distribution

__all__ = [
    "MIN_CONTRADICTIONS",
    "MIN_EMBEDDINGS",
    "MIN_GEN_MODELS",
    "MIN_RUNS",
    "QUALITY_AXES",
    "QUALITY_MARGIN",
    "REGIMES",
    "AxisDistribution",
    "CellResult",
    "Distribution",
    "Gate2Criterion",
    "Gate2Report",
    "aggregate",
    "run_distribution",
]
