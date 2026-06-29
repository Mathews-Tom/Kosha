"""Tests for embedding-aware threshold calibration and the mismatch warning."""

from __future__ import annotations

import math

import pytest

from kosha.bench.calibrate import (
    calibrate_thresholds,
    default_threshold_mismatch,
    render_calibration,
)
from kosha.bench.labels import DedupPair
from kosha.dedup.decision import DEFAULT_THRESHOLDS, Thresholds
from kosha.providers import LexicalEmbeddingProvider
from kosha.providers.base import Vector


class _StubEmbed:
    """An embedding provider returning fixed 2-D vectors so cosines are exact."""

    def __init__(self, vectors: dict[str, Vector], name: str = "stub-embed") -> None:
        self._vectors = vectors
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def dimension(self) -> int:
        return 2

    def embed(self, texts: list[str]) -> list[Vector]:
        return [self._vectors[text] for text in texts]


def _unit(cosine: float) -> Vector:
    """A unit vector whose cosine with (1, 0) is ``cosine``."""
    return [cosine, math.sqrt(1.0 - cosine * cosine)]


def _pairs() -> tuple[list[DedupPair], dict[str, Vector]]:
    base: Vector = [1.0, 0.0]
    vectors = {
        "same_hi_a": base, "same_hi_b": _unit(0.90),
        "same_lo_a": base, "same_lo_b": _unit(0.70),
        "diff_hi_a": base, "diff_hi_b": _unit(0.80),
        "diff_lo_a": base, "diff_lo_b": _unit(0.50),
    }
    pairs = [
        DedupPair("same_hi_a", "same_hi_b", "same", "clear"),
        DedupPair("same_lo_a", "same_lo_b", "same", "ambiguous"),
        DedupPair("diff_hi_a", "diff_hi_b", "different", "ambiguous"),
        DedupPair("diff_lo_a", "diff_lo_b", "different", "clear"),
    ]
    return pairs, vectors


def test_calibrate_fits_an_overlapping_band_above_diff_below_same() -> None:
    pairs, vectors = _pairs()
    calibration = calibrate_thresholds(pairs, _StubEmbed(vectors), margin=0.02)
    # high sits just above the highest different pair (0.80); low just below the
    # lowest same pair (0.70). The band brackets the overlap region.
    assert calibration.thresholds.high == pytest.approx(0.82)
    assert calibration.thresholds.low == pytest.approx(0.68)
    assert calibration.overlapping is True
    assert calibration.same_min == pytest.approx(0.70)
    assert calibration.different_max == pytest.approx(0.80)


def test_calibrate_collapses_to_one_threshold_when_separable() -> None:
    vectors = {
        "s1a": [1.0, 0.0], "s1b": _unit(0.90),
        "s2a": [1.0, 0.0], "s2b": _unit(0.85),
        "d1a": [1.0, 0.0], "d1b": _unit(0.50),
        "d2a": [1.0, 0.0], "d2b": _unit(0.40),
    }
    pairs = [
        DedupPair("s1a", "s1b", "same", "clear"),
        DedupPair("s2a", "s2b", "same", "clear"),
        DedupPair("d1a", "d1b", "different", "clear"),
        DedupPair("d2a", "d2b", "different", "clear"),
    ]
    calibration = calibrate_thresholds(pairs, _StubEmbed(vectors), margin=0.02)
    assert calibration.overlapping is False
    # Midpoint of max-different (0.50) and min-same (0.85): an empty band.
    assert calibration.thresholds.high == pytest.approx(0.675)
    assert calibration.thresholds.low == pytest.approx(0.675)


def test_calibrate_requires_both_labels() -> None:
    vectors = {"a": [1.0, 0.0], "b": _unit(0.9)}
    pairs = [DedupPair("a", "b", "same", "clear")]
    with pytest.raises(ValueError, match="both same and different"):
        calibrate_thresholds(pairs, _StubEmbed(vectors))


def test_calibrate_rejects_an_out_of_range_margin() -> None:
    pairs, vectors = _pairs()
    with pytest.raises(ValueError, match="margin"):
        calibrate_thresholds(pairs, _StubEmbed(vectors), margin=1.5)


def test_default_threshold_mismatch_warns_for_a_real_embedding() -> None:
    real = _StubEmbed({}, name="openai:bge-m3")
    message = default_threshold_mismatch(real, DEFAULT_THRESHOLDS)
    assert message is not None
    assert "openai:bge-m3" in message and "kosha calibrate" in message


def test_default_threshold_mismatch_is_silent_for_lexical_or_custom() -> None:
    # The lexical default scale is what DEFAULT_THRESHOLDS are tuned for.
    assert default_threshold_mismatch(LexicalEmbeddingProvider(), DEFAULT_THRESHOLDS) is None
    # Overridden thresholds are the operator's choice; no warning.
    real = _StubEmbed({}, name="openai:bge-m3")
    assert default_threshold_mismatch(real, Thresholds(high=0.9, low=0.6)) is None


def test_render_calibration_reports_the_fitted_thresholds() -> None:
    pairs, vectors = _pairs()
    text = render_calibration(calibrate_thresholds(pairs, _StubEmbed(vectors)))
    assert "high = 0.820" in text
    assert "low  = 0.680" in text
    assert "stub-embed" in text
