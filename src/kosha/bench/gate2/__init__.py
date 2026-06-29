"""Pre-registered Gate-0 v2 re-test (spike S2).

Gate-0 v2 re-opens the Gate-0 question after M13 tied on a tiny, clean held-out
set: *does the maintenance loop beat a good prompt on a buyer-relevant axis at
scale?* The bar — margin, sample size, regimes, provider matrix — is fixed in
:mod:`kosha.bench.gate2.criterion` BEFORE any measurement so the verdict cannot
be tuned to the result. :mod:`kosha.bench.gate2.harness` runs the matrix over N
runs to fold out default-sampling noise; :mod:`kosha.bench.gate2.distribution`
holds the pure aggregation.
"""

from __future__ import annotations

from kosha.bench.gate2.contradictions import (
    SCALES,
    ContradictionCase,
    build_contradiction_set,
    load_contradictions,
    regimes_present,
    write_contradictions,
)
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
from kosha.bench.gate2.harness import (
    AxisSample,
    CellMeasure,
    CellSample,
    aggregate_cell,
    run_gate2,
)
from kosha.bench.gate2.histories import (
    bury_in_body,
    deep_history_claims,
    render_history,
)

__all__ = [
    "MIN_CONTRADICTIONS",
    "MIN_EMBEDDINGS",
    "MIN_GEN_MODELS",
    "MIN_RUNS",
    "QUALITY_AXES",
    "QUALITY_MARGIN",
    "REGIMES",
    "SCALES",
    "AxisDistribution",
    "AxisSample",
    "CellMeasure",
    "CellResult",
    "CellSample",
    "ContradictionCase",
    "Distribution",
    "Gate2Criterion",
    "Gate2Report",
    "aggregate",
    "aggregate_cell",
    "build_contradiction_set",
    "bury_in_body",
    "deep_history_claims",
    "load_contradictions",
    "regimes_present",
    "render_history",
    "run_distribution",
    "run_gate2",
    "write_contradictions",
]
