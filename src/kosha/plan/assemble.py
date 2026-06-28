"""Assemble proposed file changes into a reviewable :class:`ChangePlan`.

The plan builder realizes ``plan(FileChange[]) -> ChangePlan`` (system_design
§2.2): it gathers every proposed write plus the contradictions the resolution
policy could not settle into one ordered, de-duplicated plan the approve gate
renders. The builder is deterministic — changes sorted by path, flags by concept —
and rejects two changes targeting the same path, the "duplicate change" the stack
review guards against.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, Field

from kosha.plan.changes import ChangeKind, FileChange


class Flag(BaseModel):
    """A conflict the resolution policy escalated — surfaced for human judgment."""

    concept_id: str
    summary: str
    detail: str = ""


class ChangePlan(BaseModel):
    """An ordered set of proposed file writes plus escalated conflicts."""

    changes: list[FileChange] = Field(default_factory=list)
    flags: list[Flag] = Field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        """True when the plan proposes no writes and raised no flags."""
        return not self.changes and not self.flags

    @property
    def creates(self) -> list[FileChange]:
        """The changes that write a new file."""
        return [c for c in self.changes if c.kind is ChangeKind.CREATE]

    @property
    def updates(self) -> list[FileChange]:
        """The changes that rewrite an existing file."""
        return [c for c in self.changes if c.kind is ChangeKind.UPDATE]

    def paths(self) -> list[str]:
        """The bundle-relative paths the plan would write, in plan order."""
        return [c.path for c in self.changes]


def build_plan(changes: Sequence[FileChange], flags: Sequence[Flag] = ()) -> ChangePlan:
    """Order ``changes`` and ``flags`` into a deterministic plan.

    Raises :class:`ValueError` if two changes target the same path: a single
    ingest writes each file once, so a collision is a pipeline bug to surface, not
    a last-write-wins to swallow.
    """
    seen: set[str] = set()
    for change in changes:
        if change.path in seen:
            raise ValueError(f"duplicate change for path {change.path!r}")
        seen.add(change.path)
    ordered = sorted(changes, key=lambda c: c.path)
    ordered_flags = sorted(flags, key=lambda f: f.concept_id)
    return ChangePlan(changes=ordered, flags=ordered_flags)
