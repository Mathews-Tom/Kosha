"""Graduated autonomy: route each change to a review lane (system_design §4.5).

"Human approves every write" breaks at volume — 200 near-identical proposals turn
a reviewer into a rubber stamp, so the gate stops gating. Kosha routes each change
by the confidence the dedup resolver already produced and the change's impact:

* ``AUTO`` — high confidence, low impact (isolated create, additive claim,
  link/index/log regen): auto-applies on the branch, reviewable after the fact.
* ``SKIM`` — medium confidence or impact, or a policy-resolved contradiction:
  applies on the branch and is surfaced in the plan.
* ``BLOCK`` — low confidence, an *escalated* contradiction, or a load-bearing
  supersede: explicit approval required before it applies.

A plan needs explicit human approval iff any change lands in ``BLOCK``; the rest
apply on the ingest branch under the delegated policy. Thresholds are per-bundle
tunable and a regulated bundle can ``force_block`` everything (§4.5).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from kosha.plan import ChangePlan, ContradictionState, FileChange, Impact


class Lane(IntEnum):
    """Review lanes, ordered by how much human attention they demand."""

    AUTO = 0
    SKIM = 1
    BLOCK = 2

    @property
    def label(self) -> str:
        return self.name.lower()


@dataclass(frozen=True)
class AutonomyThresholds:
    """Confidence cutoffs for the routing lanes (per-bundle tunable, §4.5).

    ``force_block`` routes everything to ``BLOCK`` — the regulated-bundle setting.
    """

    block_below: float = 0.4
    skim_below: float = 0.9
    force_block: bool = False

    def __post_init__(self) -> None:
        if not 0.0 <= self.block_below <= self.skim_below <= 1.0:
            raise ValueError("require 0 <= block_below <= skim_below <= 1")


DEFAULT_THRESHOLDS = AutonomyThresholds()


@dataclass(frozen=True)
class ChangeRouting:
    """One change's assigned lane and the rule that put it there."""

    change: FileChange
    lane: Lane
    reason: str


@dataclass(frozen=True)
class PlanRouting:
    """The lane assignment for every change in a plan, plus escalated flags.

    ``flagged`` counts the conflicts the resolution policy escalated (plan flags).
    An escalated conflict may hold a claim without changing any file, so it forces
    the plan to ``BLOCK`` independently of the per-change lanes.
    """

    routes: tuple[ChangeRouting, ...]
    flagged: int = 0

    @property
    def lane(self) -> Lane:
        """The strictest lane the plan reached (``AUTO`` for an empty plan)."""
        change_lane = max((route.lane for route in self.routes), default=Lane.AUTO)
        return Lane.BLOCK if self.flagged else change_lane

    @property
    def requires_approval(self) -> bool:
        """Whether the plan blocks and so needs explicit human approval."""
        return self.lane is Lane.BLOCK

    def blocked(self) -> list[ChangeRouting]:
        """The routed changes that landed in the ``BLOCK`` lane."""
        return [route for route in self.routes if route.lane is Lane.BLOCK]


def route_change(
    change: FileChange, thresholds: AutonomyThresholds = DEFAULT_THRESHOLDS
) -> ChangeRouting:
    """Assign ``change`` to a review lane by confidence, impact, and contradiction."""
    if thresholds.force_block:
        return ChangeRouting(change, Lane.BLOCK, "bundle forces all changes to block")
    if change.contradiction is ContradictionState.ESCALATED:
        return ChangeRouting(change, Lane.BLOCK, "escalated contradiction needs human judgment")
    if change.impact is Impact.HIGH:
        return ChangeRouting(change, Lane.BLOCK, "load-bearing supersede")
    if change.confidence < thresholds.block_below:
        return ChangeRouting(
            change, Lane.BLOCK, f"confidence {change.confidence:.2f} < {thresholds.block_below:.2f}"
        )
    if change.contradiction is ContradictionState.RESOLVED:
        return ChangeRouting(change, Lane.SKIM, "policy-resolved contradiction")
    if change.impact is Impact.MEDIUM:
        return ChangeRouting(change, Lane.SKIM, "medium impact")
    if change.confidence < thresholds.skim_below:
        return ChangeRouting(
            change, Lane.SKIM, f"confidence {change.confidence:.2f} < {thresholds.skim_below:.2f}"
        )
    return ChangeRouting(change, Lane.AUTO, "high confidence, low impact")


def route_plan(
    plan: ChangePlan, thresholds: AutonomyThresholds = DEFAULT_THRESHOLDS
) -> PlanRouting:
    """Route every change in ``plan`` into its review lane.

    Escalated conflicts (``plan.flags``) force the plan to block even when no
    change does, because an escalation may hold a claim without writing a file.
    """
    return PlanRouting(
        tuple(route_change(change, thresholds) for change in plan.changes),
        flagged=len(plan.flags),
    )


def render_routing(routing: PlanRouting) -> str:
    """Render the per-change lane assignment, strictest lane summarized first."""
    verb = (
        "blocked: explicit approval required"
        if routing.requires_approval
        else "auto-applies on branch"
    )
    lines = [f"Autonomy: plan lane = {routing.lane.label} ({verb})"]
    lines.extend(
        f"  [{route.lane.label}] {route.change.path} — {route.reason}" for route in routing.routes
    )
    if routing.flagged:
        lines.append(f"  {routing.flagged} escalated conflict(s) require approval")
    return "\n".join(lines)
