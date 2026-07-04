"""Per-item review: approve or reject each plan item individually (M8 PR-3).

The blanket gate in :mod:`kosha.approve.decision` asks one yes/no for a whole
plan. A reviewer who wants to keep three of five proposed changes and drop the
rest has no way to express that with a single decision. This module walks a
plan's changes (and any escalated flags) one at a time, asking a separate
default-safe :func:`~kosha.approve.decision.request_decision` for each, so
approving some items never silently approves the rest.

Escalated flags cannot be selectively "un-written" the way a file change can —
they represent a conflict the resolution policy could not settle, not a
proposed write. A rejected (unacknowledged) flag therefore withholds the whole
plan rather than a subset of it: the same "no silent mutation" default the
blanket gate already applies when any flag is present.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from kosha.approve.autonomy import ChangeRouting, PlanRouting
from kosha.approve.decision import Decision, Reader, request_decision
from kosha.approve.render import render_change_item, render_flag_item
from kosha.plan import ChangePlan, Flag

Printer = Callable[[str], None]


@dataclass(frozen=True)
class ItemReviewResult:
    """The reviewer's per-item decisions plus the derived approved subset."""

    change_decisions: dict[str, Decision] = field(default_factory=dict)
    flags_acknowledged: bool = True

    @property
    def proceeds(self) -> bool:
        """Whether any decision produced something committable.

        An unacknowledged flag withholds the whole plan (no partial commit of
        a conflict the resolution policy could not settle), independent of how
        many individual changes were approved.
        """
        return self.flags_acknowledged and any(
            decision is Decision.APPROVE for decision in self.change_decisions.values()
        )

    def approved_paths(self) -> frozenset[str]:
        """The change paths the reviewer approved."""
        if not self.flags_acknowledged:
            return frozenset()
        return frozenset(
            path for path, decision in self.change_decisions.items() if decision is Decision.APPROVE
        )


def request_item_decisions(
    plan: ChangePlan,
    routing: PlanRouting,
    reader: Reader,
    *,
    printer: Printer = print,
) -> ItemReviewResult:
    """Ask the reviewer to approve or reject each plan item individually.

    Flags are reviewed first — acknowledging every one is required before any
    change's decision can commit, matching the existing block-lane semantics
    at the whole-plan level. Each change is then shown via
    :func:`~kosha.approve.render.render_change_item` and asked a separate
    default-safe yes/no; an EOF, empty, or unparseable answer rejects only that
    item (:func:`~kosha.approve.decision.request_decision`'s existing
    default-safe behavior, applied once per item instead of once for the
    plan).
    """
    flags_acknowledged = _review_flags(plan.flags, reader, printer)
    routes_by_path: dict[str, ChangeRouting] = {
        route.change.path: route for route in routing.routes
    }
    decisions: dict[str, Decision] = {}
    for change in plan.changes:
        printer(render_change_item(change, routes_by_path.get(change.path)))
        decisions[change.path] = request_decision(
            reader, prompt=f"Approve {change.path}? [y/N] "
        )
    return ItemReviewResult(change_decisions=decisions, flags_acknowledged=flags_acknowledged)


def _review_flags(flags: list[Flag], reader: Reader, printer: Printer) -> bool:
    if not flags:
        return True
    acknowledged = True
    for flag in flags:
        printer(render_flag_item(flag))
        decision = request_decision(
            reader, prompt=f"Acknowledge escalated conflict {flag.concept_id}? [y/N] "
        )
        acknowledged = acknowledged and decision is Decision.APPROVE
    return acknowledged
