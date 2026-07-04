"""Fit every decision threshold to the configured providers on the seed labels.

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

Three more lexical surfaces gate on a single Jaccard-style cutoff rather than a
two-threshold band — :class:`~kosha.dedup.adjudicate.LexicalAdjudicator`,
:class:`~kosha.merge.update.LexicalClaimTargeter`, and
:class:`~kosha.link.relate.LexicalRelator` — and were never recalibrated for a
real embedding's score geometry (M3, analysis §1.5). :func:`calibrate_adjudicator_threshold`,
:func:`calibrate_targeter_threshold`, and :func:`calibrate_relator_threshold` fit
each one the same way: score every labeled positive/negative pair with the exact
function the surface uses at decision time, then pick whichever cutoff best
separates them on the seed set. All calibration is refused against anything but
the tracked ``labels/*_seed.jsonl`` seed files — see :func:`assert_seed_labels_path`.
"""

from __future__ import annotations

import itertools
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from kosha.bench.labels import DedupPair, _cosine
from kosha.dedup.adjudicate import jaccard_overlap as adjudicator_score
from kosha.dedup.decision import DEFAULT_THRESHOLDS, Thresholds
from kosha.link.relate import concept_text, term_overlap_score
from kosha.merge.update import jaccard_overlap as targeter_score
from kosha.model import Bundle
from kosha.providers.base import EmbeddingProvider
from kosha.providers.tokens import tokenize

_SAME = "same"
# Held-out fixtures Gate-0 measures against; calibration must never see them,
# or a threshold fit on them would overfit the very set it is graded against.
_HELD_OUT_ROOTS = ("evals/realworld/",)


class MergeCaseLike(Protocol):
    """The shape :func:`calibrate_targeter_threshold` needs from a merge case.

    Structural, not imported from :mod:`kosha.eval.merge`: ``kosha.eval``
    imports from ``kosha.bench`` (for the dedup label types), so importing the
    concrete ``MergeCase`` here would be circular. A real ``MergeCase`` already
    satisfies this shape. Read-only properties (not plain attributes) so a
    frozen dataclass's narrower field types (e.g. ``tuple[str, ...]``) satisfy
    the protocol covariantly instead of requiring an exact type match.
    """

    @property
    def existing(self) -> Sequence[str]: ...
    @property
    def update(self) -> str: ...
    @property
    def target(self) -> int: ...


class RelateCaseLike(Protocol):
    """The shape :func:`calibrate_relator_threshold` needs from a relate case.

    Structural for the same reason as :class:`MergeCaseLike` — avoids importing
    ``kosha.eval.relate``, which would cycle back through ``kosha.bench``.
    """

    @property
    def bundle(self) -> Bundle: ...
    @property
    def gold(self) -> frozenset[tuple[str, str]]: ...


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


def assert_seed_labels_path(path: Path) -> None:
    """Refuse to calibrate against a held-out fixture instead of a seed label file.

    Calibration must only ever fit against the tracked ``labels/*_seed.jsonl``
    seed sets (system_design §4.5); fitting a threshold on the held-out
    ``evals/realworld`` maintenance/query fixtures would let Gate-0 measure a
    threshold tuned on the very data it is supposed to generalize to.
    """
    normalized = path.as_posix()
    for root in _HELD_OUT_ROOTS:
        if root in normalized:
            raise ValueError(
                f"refusing to calibrate on a held-out fixture path: {path} "
                f"(contains {root!r}); calibrate only against labels/*_seed.jsonl"
            )


@dataclass(frozen=True)
class SingleThresholdCalibration:
    """A fitted single-cutoff threshold plus the seed score distribution.

    Unlike the embedding two-threshold band, :class:`LexicalAdjudicator`,
    :class:`~kosha.merge.update.LexicalClaimTargeter`, and
    :class:`~kosha.link.relate.LexicalRelator` each gate on one cutoff: ``score
    >= threshold`` is a positive call. ``threshold`` is whichever cutoff
    maximizes accuracy separating the seed set's positive and negative scores.
    """

    surface: str
    threshold: float
    case_count: int
    positive_count: int
    negative_count: int
    positive_min: float
    positive_max: float
    negative_min: float
    negative_max: float
    fit_score: float


def _fit_single_threshold(positive: list[float], negative: list[float]) -> tuple[float, float]:
    """Return ``(threshold, balanced_accuracy)`` for the best-separating cutoff.

    Candidates are the midpoints between consecutive distinct scores across both
    classes (plus the [0, 1] bounds), so the fit depends only on the seed
    distribution, never an arbitrary fixed margin. Scored by *balanced* accuracy
    — the mean of the true-positive and true-negative rate — rather than raw
    accuracy: the relator's cross-case negative sampling produces far more
    negative than positive examples, and plain accuracy on an imbalanced set is
    maximized by a threshold that rejects everything.
    """
    scores = sorted(set(positive) | set(negative))
    candidates = {0.0, 1.0}
    candidates.update((a + b) / 2.0 for a, b in itertools.pairwise(scores))
    best_threshold, best_balanced = 0.0, -1.0
    for candidate in sorted(candidates):
        true_positive_rate = sum(1 for s in positive if s >= candidate) / len(positive)
        true_negative_rate = sum(1 for s in negative if s < candidate) / len(negative)
        balanced = (true_positive_rate + true_negative_rate) / 2.0
        if balanced > best_balanced:
            best_threshold, best_balanced = candidate, balanced
    return best_threshold, best_balanced


def _single_threshold_calibration(
    surface: str, positive: list[float], negative: list[float]
) -> SingleThresholdCalibration:
    if not positive or not negative:
        raise ValueError(f"{surface} calibration needs both positive and negative labeled cases")
    threshold, fit_score = _fit_single_threshold(positive, negative)
    return SingleThresholdCalibration(
        surface=surface,
        threshold=threshold,
        case_count=len(positive) + len(negative),
        positive_count=len(positive),
        negative_count=len(negative),
        positive_min=min(positive),
        positive_max=max(positive),
        negative_min=min(negative),
        negative_max=max(negative),
        fit_score=fit_score,
    )


def calibrate_adjudicator_threshold(pairs: list[DedupPair]) -> SingleThresholdCalibration:
    """Fit ``LexicalAdjudicator.same_threshold`` to the seed dedup pairs.

    Scores every pair with the exact Jaccard function the adjudicator calls at
    decision time, so the fitted threshold reproduces the deployed behavior.
    """
    if not pairs:
        raise ValueError("no dedup pairs to calibrate on")
    positive = [adjudicator_score(pair.a, pair.b) for pair in pairs if pair.label == _SAME]
    negative = [adjudicator_score(pair.a, pair.b) for pair in pairs if pair.label != _SAME]
    return _single_threshold_calibration("adjudicator", positive, negative)


def calibrate_targeter_threshold(cases: Sequence[MergeCaseLike]) -> SingleThresholdCalibration:
    """Fit ``LexicalClaimTargeter.threshold`` to the seed merge cases.

    For each case, the update's score against its labeled target claim is a
    positive example; its score against every other existing claim (including
    every claim in a ``NOVEL`` case) is a negative example — exactly the
    same/other split the targeter's best-score-above-threshold rule needs.
    """
    if not cases:
        raise ValueError("no merge cases to calibrate on")
    positive: list[float] = []
    negative: list[float] = []
    for case in cases:
        for index, existing in enumerate(case.existing):
            score = targeter_score(case.update, existing)
            (positive if index == case.target else negative).append(score)
    return _single_threshold_calibration("targeter", positive, negative)


def calibrate_relator_threshold(cases: Sequence[RelateCaseLike]) -> SingleThresholdCalibration:
    """Fit ``LexicalRelator.threshold`` to the seed relate cases.

    Every seed case is a small mini-bundle built so its concepts *do* relate —
    there is no in-case unrelated pair to serve as a negative example. Negatives
    instead come from cross-case pairs: a concept from one mini-bundle scored
    against a concept from another is never a gold edge in any case, and the
    mini-bundles are deliberately built on distinct topics, so that pairing is a
    real "these are unrelated" signal, not a synthetic one. Every pair is scored
    with the exact term/tag overlap function the relator calls at decision time.
    """
    if not cases:
        raise ValueError("no relate cases to calibrate on")
    bundles = [list(case.bundle.concepts.values()) for case in cases]
    positive: list[float] = []
    negative: list[float] = []
    for case_index, case in enumerate(cases):
        for source in bundles[case_index]:
            source_terms = set(tokenize(concept_text(source)))
            source_tags = {tag.lower() for tag in source.frontmatter.tags}
            for candidate in bundles[case_index]:
                if candidate.concept_id == source.concept_id:
                    continue
                score = term_overlap_score(source_terms, source_tags, candidate)
                is_gold = (source.concept_id, candidate.concept_id) in case.gold
                (positive if is_gold else negative).append(score)
            for other_index, other_bundle in enumerate(bundles):
                if other_index == case_index:
                    continue
                for candidate in other_bundle:
                    negative.append(term_overlap_score(source_terms, source_tags, candidate))
    return _single_threshold_calibration("relator", positive, negative)


def render_single_threshold_calibration(calibration: SingleThresholdCalibration) -> str:
    """Render a fitted single-cutoff threshold and its seed score distribution."""
    return "\n".join(
        [
            f"Calibrated {calibration.surface} threshold on {calibration.case_count} seed "
            f"cases (fit score {calibration.fit_score:.3f}):",
            f"  threshold = {calibration.threshold:.3f}",
            f"  positive ({calibration.positive_count}): score "
            f"{calibration.positive_min:.3f}-{calibration.positive_max:.3f}",
            f"  negative ({calibration.negative_count}): score "
            f"{calibration.negative_min:.3f}-{calibration.negative_max:.3f}",
        ]
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
