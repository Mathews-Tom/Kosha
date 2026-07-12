"""Render a :class:`~kosha.plan.ChangePlan` as a reviewable text plan.

The approve gate is CLI-first (system_design §8.1 "CLI first"): before any write,
the plan is shown as create/update lines plus the escalated conflicts a human must
judge. Rendering is deterministic — the plan is already ordered — and annotates
each change with the provenance the autonomy router reads (confidence, impact, and
whether a contradiction was resolved or escalated), so a reviewer sees *why* a
change needs (or does not need) their attention. A change whose evidence carries
non-``complete`` coverage (DEVELOPMENT_PLAN.md M5) is annotated the same way
(``coverage=<kind>``) in both this summary view and the per-item review view;
the per-item view (:func:`render_change_item`) additionally lists each
structured coverage warning, so a reviewer deciding one change at a time never
mistakes a bounded or incremental retrieval for an exhaustive one.
"""

from __future__ import annotations

from kosha.approve.autonomy import ChangeRouting
from kosha.evidence.model import CoverageKind
from kosha.plan import ChangePlan, ContradictionState, FileChange, Flag


def render_plan(plan: ChangePlan) -> str:
    """Render ``plan`` as a multi-line, reviewable change plan."""
    if plan.is_empty:
        return "Change plan: no changes."
    header = f"Change plan: {len(plan.changes)} change(s), {len(plan.flags)} flag(s)"
    lines = [header]
    updates = plan.updates
    creates = plan.creates
    if updates:
        lines.append("")
        lines.append("Updates:")
        lines.extend(_change_line(change) for change in updates)
    if creates:
        lines.append("")
        lines.append("Creates:")
        lines.extend(_change_line(change) for change in creates)
    if plan.flags:
        lines.append("")
        lines.append("Flags (need human judgment):")
        lines.extend(f"  {flag.concept_id}: {flag.summary}" for flag in plan.flags)
    return "\n".join(lines)


def _change_line(change: FileChange) -> str:
    summary = f" — {change.summary}" if change.summary else ""
    return f"  [{change.kind.value}] {change.path}{summary}  {_annotations(change)}"


def _annotations(change: FileChange) -> str:
    parts = [f"conf={change.confidence:.2f}", f"impact={change.impact.value}"]
    if change.contradiction is not ContradictionState.NONE:
        parts.append(f"contradiction={change.contradiction.value}")
    if change.coverage is not None and change.coverage.kind is not CoverageKind.COMPLETE:
        parts.append(f"coverage={change.coverage.kind.value}")
    return f"[{' '.join(parts)}]"


def render_change_item(change: FileChange, route: ChangeRouting | None = None) -> str:
    """Render one change as a standalone reviewable block (the per-item review flow).

    Unlike :func:`render_plan`'s single summary line per change, this shows
    enough context to decide on the change in isolation — path, kind, summary,
    provenance, and (when routed) the lane and reason it was assigned, since a
    per-item reviewer sees one change at a time rather than the whole plan.
    """
    lines = [f"[{change.kind.value}] {change.path}"]
    if change.summary:
        lines.append(f"  summary: {change.summary}")
    lines.append(f"  {_annotations(change)}")
    if change.coverage is not None:
        lines.extend(f"  coverage warning: {warning}" for warning in change.coverage.warnings)
    if route is not None:
        lines.append(f"  lane={route.lane.label} ({route.reason})")
    return "\n".join(lines)


def render_flag_item(flag: Flag) -> str:
    """Render one escalated conflict as a standalone reviewable block."""
    lines = [f"[flag] {flag.concept_id}: {flag.summary}"]
    if flag.detail:
        lines.append(f"  {flag.detail}")
    return "\n".join(lines)
