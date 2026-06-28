"""Render a :class:`~kosha.plan.ChangePlan` as a reviewable text plan.

The approve gate is CLI-first (system_design §8.1 "CLI first"): before any write,
the plan is shown as create/update lines plus the escalated conflicts a human must
judge. Rendering is deterministic — the plan is already ordered — and annotates
each change with the provenance the autonomy router reads (confidence, impact, and
whether a contradiction was resolved or escalated), so a reviewer sees *why* a
change needs (or does not need) their attention.
"""

from __future__ import annotations

from kosha.plan import ChangePlan, ContradictionState, FileChange


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
    return f"[{' '.join(parts)}]"
