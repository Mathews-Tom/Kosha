"""Fit the two-threshold dedup band to a configured embedding on the seed labels.

``DEFAULT_THRESHOLDS`` (``high=0.95``, ``low=0.15``) are tuned for the local
lexical embedding: a re-ingest self-matches at cosine ~1.0 and clearly-unrelated
text scores < 0.15. A real semantic embedding lives on a different scale — bge-m3
scores genuine duplicates around 0.72-0.79 and clearly-different pairs around
0.5 — so the lexical ``high`` is unreachable (every ingest then adjudicates) and
``low`` lets too little auto-create.

:func:`calibrate_thresholds` fits the band to whatever embedding is configured,
on the **seed** dedup labels only (never the held-out maintenance set):

* ``high`` sits just above the highest *different*-pair cosine, so an auto-UPDATE
  on the top neighbor cannot fire on a pair the seed set knows is different —
  duplicates whose top score is below it still go through multi-candidate
  selection rather than blindly attaching to rank 0;
* ``low`` sits just below the lowest *same*-pair cosine, so clearly-novel drafts
  auto-create without an LLM call and no known-same pair is auto-created.

When the same/different cosines do not overlap the band collapses to the single
separating threshold. The fit is a per-bundle tunable (system_design §4.5); it
never touches the held-out set, so it cannot overfit the benchmark.
"""

from __future__ import annotations

from dataclasses import dataclass

from kosha.bench.labels import DedupPair, _cosine
from kosha.dedup.decision import DEFAULT_THRESHOLDS, Thresholds
from kosha.providers.base import EmbeddingProvider

_SAME = "same"


@dataclass(frozen=True)
class Calibration:
    """Fitted thresholds plus the seed-label score distribution they came from."""

    thresholds: Thresholds
    provider: str
    pair_count: int
    same_count: int
    different_count: int
    same_min: float
    same_max: float
    different_min: float
    different_max: float
    margin: float
    overlapping: bool


def calibrate_thresholds(
    pairs: list[DedupPair], provider: EmbeddingProvider, *, margin: float = 0.02
) -> Calibration:
    """Fit ``Thresholds`` to ``provider`` over the labeled seed ``pairs``."""
    if not pairs:
        raise ValueError("no dedup pairs to calibrate on")
    if not 0.0 <= margin <= 1.0:
        raise ValueError("margin must be in [0, 1]")
    same: list[float] = []
    different: list[float] = []
    for pair in pairs:
        score = _cosine(*provider.embed([pair.a, pair.b]))
        (same if pair.label == _SAME else different).append(score)
    if not same or not different:
        raise ValueError("calibration needs both same and different labeled pairs")

    same_min, same_max = min(same), max(same)
    different_min, different_max = min(different), max(different)
    # high: above every known-different pair -> a top-neighbor auto-UPDATE never
    # fires on a pair the seed knows is different. low: below every known-same
    # pair -> clearly-novel drafts auto-create and no same pair is auto-created.
    high_candidate = different_max + margin
    low_candidate = same_min - margin
    overlapping = high_candidate >= low_candidate
    if overlapping:
        high = max(0.0, min(1.0, high_candidate))
        low = max(0.0, min(1.0, low_candidate))
    else:
        # Separable on the seed: collapse to a single threshold (empty band).
        separator = (different_max + same_min) / 2.0
        high = low = max(0.0, min(1.0, separator))
    low = min(low, high)
    return Calibration(
        thresholds=Thresholds(high=high, low=low),
        provider=provider.name,
        pair_count=len(pairs),
        same_count=len(same),
        different_count=len(different),
        same_min=same_min,
        same_max=same_max,
        different_min=different_min,
        different_max=different_max,
        margin=margin,
        overlapping=overlapping,
    )


def default_threshold_mismatch(
    provider: EmbeddingProvider, thresholds: Thresholds
) -> str | None:
    """Return a warning when lexical-tuned defaults are used with a real embedding.

    ``DEFAULT_THRESHOLDS`` are calibrated for the local lexical embedding; a
    semantic embedding scores duplicates on a different scale, so reusing the
    defaults silently routes every ingest through the LLM adjudicator. Returns
    ``None`` when the defaults are fine (lexical provider) or the thresholds were
    already overridden.
    """
    if thresholds == DEFAULT_THRESHOLDS and not provider.name.startswith("lexical"):
        return (
            f"embedding '{provider.name}' is not the local lexical default, but "
            f"DEFAULT_THRESHOLDS (high={DEFAULT_THRESHOLDS.high}, low={DEFAULT_THRESHOLDS.low}) "
            "are calibrated for that lexical scale, so this run may route every ingest "
            "through the LLM adjudicator. Run `kosha calibrate --labels "
            "labels/dedup_seed.jsonl` to fit the band for this embedding and configure the "
            "fitted thresholds where the resolver is invoked."
        )
    return None


def render_calibration(calibration: Calibration) -> str:
    """Render the fitted thresholds and the seed score distribution as text."""
    band = "overlapping" if calibration.overlapping else "separable (collapsed band)"
    return "\n".join(
        [
            f"Calibrated thresholds for embedding '{calibration.provider}' "
            f"on {calibration.pair_count} seed pairs (margin {calibration.margin}):",
            f"  high = {calibration.thresholds.high:.3f}  (>= high -> auto-UPDATE)",
            f"  low  = {calibration.thresholds.low:.3f}  (<  low  -> auto-CREATE)",
            f"  same pairs ({calibration.same_count}): "
            f"cosine {calibration.same_min:.3f}-{calibration.same_max:.3f}",
            f"  different pairs ({calibration.different_count}): "
            f"cosine {calibration.different_min:.3f}-{calibration.different_max:.3f}",
            f"  same/different score ranges: {band}",
        ]
    )
