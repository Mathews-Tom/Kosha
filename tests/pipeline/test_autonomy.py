"""Graduated autonomy: confidence/impact routing lanes (M10 PR-4)."""

from __future__ import annotations

import pytest

from kosha.approve import (
    AutonomyThresholds,
    Lane,
    route_change,
    route_plan,
)
from kosha.approve.autonomy import render_routing
from kosha.plan import ChangeKind, ContradictionState, FileChange, Impact, build_plan


def _change(
    path: str = "c.md",
    *,
    confidence: float = 1.0,
    impact: Impact = Impact.LOW,
    contradiction: ContradictionState = ContradictionState.NONE,
    kind: ChangeKind = ChangeKind.CREATE,
) -> FileChange:
    return FileChange(
        path=path,
        kind=kind,
        content="x",
        confidence=confidence,
        impact=impact,
        contradiction=contradiction,
    )


def test_high_confidence_low_impact_routes_auto() -> None:
    assert route_change(_change()).lane is Lane.AUTO


def test_escalated_contradiction_blocks() -> None:
    route = route_change(_change(contradiction=ContradictionState.ESCALATED))
    assert route.lane is Lane.BLOCK
    assert "escalated" in route.reason


def test_high_impact_blocks() -> None:
    assert route_change(_change(impact=Impact.HIGH)).lane is Lane.BLOCK


def test_low_confidence_blocks() -> None:
    route = route_change(_change(confidence=0.2))
    assert route.lane is Lane.BLOCK
    assert "confidence" in route.reason


def test_resolved_contradiction_routes_skim() -> None:
    route = route_change(_change(confidence=1.0, contradiction=ContradictionState.RESOLVED))
    assert route.lane is Lane.SKIM


def test_medium_impact_routes_skim() -> None:
    assert route_change(_change(impact=Impact.MEDIUM)).lane is Lane.SKIM


def test_mid_confidence_routes_skim() -> None:
    assert route_change(_change(confidence=0.5)).lane is Lane.SKIM


def test_force_block_overrides_an_otherwise_auto_change() -> None:
    thresholds = AutonomyThresholds(force_block=True)
    assert route_change(_change(), thresholds).lane is Lane.BLOCK


def test_invalid_thresholds_rejected() -> None:
    with pytest.raises(ValueError, match="block_below"):
        AutonomyThresholds(block_below=0.9, skim_below=0.4)


def test_plan_with_only_auto_changes_needs_no_approval() -> None:
    plan = build_plan([_change("a.md"), _change("b.md")])
    routing = route_plan(plan)
    assert routing.lane is Lane.AUTO
    assert routing.requires_approval is False
    assert routing.blocked() == []


def test_plan_lane_is_the_strictest_change_lane() -> None:
    plan = build_plan(
        [
            _change("a.md"),
            _change("b.md", impact=Impact.MEDIUM),
        ]
    )
    routing = route_plan(plan)
    assert routing.lane is Lane.SKIM
    assert routing.requires_approval is False


def test_any_block_change_requires_approval() -> None:
    plan = build_plan(
        [
            _change("a.md"),
            _change("b.md", contradiction=ContradictionState.ESCALATED),
        ]
    )
    routing = route_plan(plan)
    assert routing.lane is Lane.BLOCK
    assert routing.requires_approval is True
    assert [r.change.path for r in routing.blocked()] == ["b.md"]


def test_empty_plan_routes_auto_without_approval() -> None:
    routing = route_plan(build_plan([]))
    assert routing.lane is Lane.AUTO
    assert routing.requires_approval is False


def test_render_routing_reports_plan_lane_and_each_change() -> None:
    plan = build_plan([_change("a.md", contradiction=ContradictionState.ESCALATED)])
    text = render_routing(route_plan(plan))
    assert "plan lane = block" in text
    assert "explicit approval required" in text
    assert "[block] a.md" in text


def test_escalation_flag_forces_plan_to_block() -> None:
    from kosha.plan import Flag

    plan = build_plan([_change("a.md")], [Flag(concept_id="policies/returns", summary="conflict")])
    routing = route_plan(plan)
    assert routing.lane is Lane.BLOCK
    assert routing.requires_approval is True
    assert routing.flagged == 1
    assert "escalated conflict(s) require approval" in render_routing(routing)
