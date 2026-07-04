"""Approve gate: render a change plan and capture an approve/reject decision.

The approve package realizes the Approve UI/CLI component (system_design §2.2,
§4.1): :func:`render_plan` shows the create/update/flag plan, and
:func:`request_decision` captures a default-safe yes/no so no write reaches Git
without an explicit approval (§1 "Every write is reviewable").
"""

from __future__ import annotations

from kosha.approve.autonomy import (
    DEFAULT_THRESHOLDS,
    AutonomyEvalCase,
    AutonomyEvalReport,
    AutonomyThresholds,
    ChangeRouting,
    Lane,
    PlanRouting,
    evaluate_autonomy_confidence,
    render_routing,
    route_change,
    route_plan,
)
from kosha.approve.decision import Decision, Reader, parse_decision, request_decision
from kosha.approve.render import render_plan

__all__ = [
    "DEFAULT_THRESHOLDS",
    "AutonomyEvalCase",
    "AutonomyEvalReport",
    "AutonomyThresholds",
    "ChangeRouting",
    "Decision",
    "Lane",
    "PlanRouting",
    "Reader",
    "evaluate_autonomy_confidence",
    "parse_decision",
    "render_plan",
    "render_routing",
    "request_decision",
    "route_change",
    "route_plan",
]
