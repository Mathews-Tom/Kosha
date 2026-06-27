"""Tests for two-threshold routing and the threshold value object."""

from __future__ import annotations

import pytest

from kosha.dedup import DEFAULT_THRESHOLDS, Route, Thresholds, route_candidates
from kosha.index.embedding import Neighbor

THR = Thresholds(high=0.9, low=0.2)


def _candidates(*scores: float) -> list[Neighbor]:
    return [Neighbor(f"c{i}", s) for i, s in enumerate(scores)]


def test_high_score_routes_to_update() -> None:
    routing = route_candidates(_candidates(0.95, 0.1), THR)
    assert routing.route is Route.UPDATE
    assert routing.candidate is not None and routing.candidate.concept_id == "c0"
    assert routing.score == 0.95
    assert "UPDATE" in routing.rationale


def test_low_score_routes_to_create() -> None:
    routing = route_candidates(_candidates(0.1), THR)
    assert routing.route is Route.CREATE
    assert "CREATE" in routing.rationale


def test_mid_band_routes_to_adjudicate() -> None:
    routing = route_candidates(_candidates(0.5), THR)
    assert routing.route is Route.ADJUDICATE
    assert "adjudicate" in routing.rationale


def test_no_candidates_routes_to_create() -> None:
    routing = route_candidates([], THR)
    assert routing.route is Route.CREATE
    assert routing.candidate is None
    assert routing.score == 0.0


def test_high_boundary_is_inclusive_low_boundary_is_inclusive_of_band() -> None:
    # score == high -> UPDATE (>= high); score == low -> ADJUDICATE ([low, high)).
    assert route_candidates(_candidates(0.9), THR).route is Route.UPDATE
    assert route_candidates(_candidates(0.2), THR).route is Route.ADJUDICATE
    # Just below low falls out of the band into CREATE.
    assert route_candidates(_candidates(0.199), THR).route is Route.CREATE


def test_routing_uses_only_the_top_candidate() -> None:
    # A strong runner-up never overrides a weak top candidate.
    routing = route_candidates(_candidates(0.1, 0.99), THR)
    assert routing.route is Route.CREATE


def test_default_thresholds_bracket_the_lexical_band() -> None:
    assert DEFAULT_THRESHOLDS.high == 0.95
    assert DEFAULT_THRESHOLDS.low == 0.15


def test_thresholds_reject_inverted_or_out_of_range() -> None:
    with pytest.raises(ValueError, match="low <= high"):
        Thresholds(high=0.2, low=0.8)
    with pytest.raises(ValueError, match="low <= high"):
        Thresholds(high=1.5, low=0.1)
    with pytest.raises(ValueError, match="low <= high"):
        Thresholds(high=0.5, low=-0.1)
