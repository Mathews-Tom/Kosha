"""The unit of a change plan: one reviewable :class:`FileChange`.

A :class:`FileChange` is a complete, self-describing proposed write — the path, the
full content to write on apply, and the *provenance* the governance gate reads to
decide how much human attention it needs (system_design §4.5 graduated autonomy):

* ``confidence`` — the dedup decision's confidence: ``1.0`` for a deterministic
  change (index/log regen, a clear-band create/update) and lower when the
  ambiguous-band LLM was reached.
* ``impact`` — how load-bearing the change is: additive/isolated (LOW), a
  supersede of an in-force claim or a resolved contradiction (MEDIUM), or an
  unresolved conflict / load-bearing supersede (HIGH).
* ``contradiction`` — whether a contradiction was involved and, if so, whether the
  resolution policy settled it or escalated it to the human.
* ``coverage`` — what portion of the source this change's evidence observed
  (DEVELOPMENT_PLAN.md M5), separate from the source's authority: ``None`` when
  the change carries no evidence link, otherwise the originating
  :class:`~kosha.evidence.SourceRun`'s coverage classification.

The change carries the *what*; :mod:`kosha.approve.autonomy` reads these signals
for the *how much review*. Keeping them on the change means the routing layer adds
no new model, only an interpretation.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from kosha.evidence.model import SourceCoverage


class ChangeKind(StrEnum):
    """Whether a change writes a new file or rewrites an existing one."""

    CREATE = "create"
    UPDATE = "update"


class Impact(StrEnum):
    """How load-bearing a change is — the impact axis of the autonomy routing."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ContradictionState(StrEnum):
    """Whether a change involved a contradiction, and how it was settled."""

    NONE = "none"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class FileChange(BaseModel):
    """One proposed file write, with the provenance the governance gate routes on."""

    path: str
    kind: ChangeKind
    content: str
    summary: str = ""
    concept_id: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    impact: Impact = Impact.LOW
    contradiction: ContradictionState = ContradictionState.NONE
    secret_detectors: frozenset[str] = Field(default_factory=frozenset)
    evidence_sha256: frozenset[str] = Field(default_factory=frozenset)
    coverage: SourceCoverage | None = None
