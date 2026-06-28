"""Plan builder: assemble proposed changes into a reviewable change plan.

The plan package realizes the deterministic Plan-builder component (system_design
§2.2, §4.1): the maintenance loop produces a set of :class:`FileChange`s (new and
updated concepts, regenerated indexes, the appended log) and escalated conflicts,
and :func:`build_plan` gathers them into one ordered :class:`ChangePlan` for the
approve gate to render and the autonomy router to route.
"""

from __future__ import annotations

from kosha.plan.assemble import ChangePlan, Flag, build_plan
from kosha.plan.changes import ChangeKind, ContradictionState, FileChange, Impact

__all__ = [
    "ChangeKind",
    "ChangePlan",
    "ContradictionState",
    "FileChange",
    "Flag",
    "Impact",
    "build_plan",
]
