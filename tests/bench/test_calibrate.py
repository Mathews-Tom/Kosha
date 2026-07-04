"""Tests for embedding-aware threshold calibration and the mismatch warning."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import pytest

from kosha.bench.calibrate import (
    assert_seed_labels_path,
    calibrate_adjudicator_threshold,
    calibrate_relator_threshold,
    calibrate_targeter_threshold,
    calibrate_thresholds,
    default_threshold_mismatch,
    render_calibration,
    render_single_threshold_calibration,
)
from kosha.bench.labels import DedupPair
from kosha.dedup.decision import DEFAULT_THRESHOLDS, Thresholds
from kosha.model import Bundle, Concept, Frontmatter
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


def test_assert_seed_labels_path_refuses_the_held_out_realworld_fixtures() -> None:
    with pytest.raises(ValueError, match="held-out"):
        assert_seed_labels_path(Path("evals/realworld/maintenance.jsonl"))


def test_assert_seed_labels_path_accepts_a_seed_label_file() -> None:
    assert_seed_labels_path(Path("labels/dedup_seed.jsonl"))  # does not raise


def test_calibrate_adjudicator_threshold_separates_same_from_different() -> None:
    pairs = [
        DedupPair("Gold members get free shipping.", "Gold members get free shipping now.",
                  "same", "clear"),
        DedupPair("Returns close after 30 days.", "The return window is 30 days.",
                  "same", "clear"),
        DedupPair("Gold members get free shipping.", "Refunds post to the original card.",
                  "different", "clear"),
        DedupPair("Returns close after 30 days.", "Support is open around the clock.",
                  "different", "clear"),
    ]
    calibration = calibrate_adjudicator_threshold(pairs)
    assert calibration.surface == "adjudicator"
    assert calibration.positive_count == 2
    assert calibration.negative_count == 2
    assert calibration.negative_max < calibration.threshold <= calibration.positive_min
    assert calibration.fit_score == 1.0


def test_calibrate_adjudicator_threshold_rejects_a_single_label_class() -> None:
    pairs = [DedupPair("a b c", "a b c", "same", "clear")]
    with pytest.raises(ValueError, match="adjudicator calibration needs both"):
        calibrate_adjudicator_threshold(pairs)


def test_calibrate_adjudicator_threshold_rejects_no_pairs() -> None:
    with pytest.raises(ValueError, match="no dedup pairs"):
        calibrate_adjudicator_threshold([])


@dataclass(frozen=True)
class _FakeMergeCase:
    existing: tuple[str, ...]
    update: str
    target: int


def test_calibrate_targeter_threshold_separates_targeted_from_other_claims() -> None:
    cases = [
        _FakeMergeCase(
            existing=("Standard returns are accepted within 30 days.",
                      "Gold members receive free return shipping."),
            update="Standard returns are now accepted within 45 days.",
            target=0,
        ),
        _FakeMergeCase(
            existing=("Refunds post to the original payment card.",),
            update="Expedited orders ship within one business day.",
            target=-1,
        ),
    ]
    calibration = calibrate_targeter_threshold(cases)
    assert calibration.surface == "targeter"
    assert calibration.positive_count == 1
    assert calibration.negative_count == 2
    assert calibration.negative_max < calibration.threshold <= calibration.positive_min


def test_calibrate_targeter_threshold_rejects_no_cases() -> None:
    with pytest.raises(ValueError, match="no merge cases"):
        calibrate_targeter_threshold([])


@dataclass(frozen=True)
class _FakeRelateCase:
    bundle: Bundle
    gold: frozenset[tuple[str, str]]


def _concept(concept_id: str, text: str, tags: list[str]) -> Concept:
    return Concept(
        concept_id=concept_id,
        frontmatter=Frontmatter(type="Concept", title=concept_id, description=text, tags=tags),
        body=text,
    )


def test_calibrate_relator_threshold_uses_cross_case_pairs_as_negatives() -> None:
    # Every seed case is built so its own concepts relate (no in-case negative),
    # so the negatives must come from cross-case pairs, and a fit must still
    # succeed with a threshold that separates gold in-case pairs from them.
    returns = _concept("policies/returns", "returns window for unworn items", ["returns"])
    refunds = _concept("policies/refunds", "refund to the original payment card", ["returns"])
    case_a = _FakeRelateCase(
        bundle=Bundle(root_path="eval://a", concepts={
            returns.concept_id: returns, refunds.concept_id: refunds,
        }),
        gold=frozenset({(returns.concept_id, refunds.concept_id),
                        (refunds.concept_id, returns.concept_id)}),
    )
    galaxy = _concept("astronomy/galaxy", "a galaxy contains billions of stars", ["astronomy"])
    nebula = _concept("astronomy/nebula", "a nebula is a cloud of gas and dust", ["astronomy"])
    case_b = _FakeRelateCase(
        bundle=Bundle(root_path="eval://b", concepts={
            galaxy.concept_id: galaxy, nebula.concept_id: nebula,
        }),
        gold=frozenset({(galaxy.concept_id, nebula.concept_id),
                        (nebula.concept_id, galaxy.concept_id)}),
    )
    calibration = calibrate_relator_threshold([case_a, case_b])
    assert calibration.surface == "relator"
    assert calibration.positive_count == 4  # both directions, in each of the 2 cases
    assert calibration.negative_count == 8  # 2 sources x 2 cross-case concepts, x2 cases
    assert calibration.negative_max < calibration.threshold <= calibration.positive_min


def test_calibrate_relator_threshold_rejects_no_cases() -> None:
    with pytest.raises(ValueError, match="no relate cases"):
        calibrate_relator_threshold([])


def test_fit_single_threshold_is_robust_to_class_imbalance() -> None:
    # A degenerate accuracy-only fit collapses to "reject everything" when
    # negatives vastly outnumber positives; balanced accuracy must not.
    pairs = (
        [DedupPair(f"same {i}", f"same {i} restated", "same", "clear") for i in range(3)]
        + [
            DedupPair(f"different {i} alpha", f"different {i} beta", "different", "clear")
            for i in range(60)
        ]
    )
    calibration = calibrate_adjudicator_threshold(pairs)
    assert calibration.threshold < 1.0


def test_render_single_threshold_calibration_reports_the_fit() -> None:
    pairs = [
        DedupPair("same text here", "same text here too", "same", "clear"),
        DedupPair("same text here", "completely unrelated content", "different", "clear"),
    ]
    text = render_single_threshold_calibration(calibrate_adjudicator_threshold(pairs))
    assert "adjudicator" in text
    assert "threshold = " in text
