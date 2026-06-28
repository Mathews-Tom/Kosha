"""Approve gate: render a change plan and capture an approve/reject decision.

The approve package realizes the Approve UI/CLI component (system_design §2.2,
§4.1): :func:`render_plan` shows the create/update/flag plan, and
:func:`request_decision` captures a default-safe yes/no so no write reaches Git
without an explicit approval (§1 "Every write is reviewable").
"""

from __future__ import annotations

from kosha.approve.decision import Decision, Reader, parse_decision, request_decision
from kosha.approve.render import render_plan

__all__ = [
    "Decision",
    "Reader",
    "parse_decision",
    "render_plan",
    "request_decision",
]
