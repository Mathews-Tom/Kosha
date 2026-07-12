"""Deterministic, evidence-backed knowledge-gap contracts (DEVELOPMENT_PLAN.md M10).

A :class:`KnowledgeGap` never originates from free-form model speculation --
every gap is minted by a deterministic producer in :mod:`kosha.gaps.produce`
from an already-computed, objective insufficiency signal (an ingest commit's
evidence provenance, a change's coverage classification). This module owns
only the contract and its lifecycle transitions; producing events and
persisting/deduplicating them live in :mod:`kosha.gaps.produce` and
:mod:`kosha.gaps.ledger` respectively.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from kosha.security.secret_scan import scan_text

_MAX_OPERATOR_TEXT_CHARS = 500
_GAP_ID_RE = re.compile(r"^[0-9a-f]{64}$")


class GapKind(StrEnum):
    """The objective insufficiency category a gap was minted from.

    Exactly the categories the DEVELOPMENT_PLAN.md M10 entry gate requires
    committed evidence for before any implementation may ship: at least two
    of missing/legacy evidence, incomplete coverage, missing temporal
    validity, cursor discontinuity, or unresolved source identity. This
    train evidences and implements the first two; see
    :mod:`kosha.gaps.produce` for the producers.
    """

    LEGACY_EVIDENCE = "legacy_evidence"
    INCOMPLETE_COVERAGE = "incomplete_coverage"


class GapReasonCode(StrEnum):
    """A deterministic, fixed-vocabulary explanation for one gap's kind.

    Never free text: a model or operator cannot invent a reason code, only
    select one a deterministic producer already assigned.
    """

    MISSING_SOURCE_RUN_TRAILER = "missing_source_run_trailer"
    MISSING_EVIDENCE_SHA256 = "missing_evidence_sha256"
    COVERAGE_WINDOWED = "coverage_windowed"
    COVERAGE_CURSOR_INCREMENTAL = "coverage_cursor_incremental"
    COVERAGE_SAMPLED = "coverage_sampled"
    COVERAGE_BEST_EFFORT = "coverage_best_effort"
    COVERAGE_UNKNOWN = "coverage_unknown"


class GapStatus(StrEnum):
    """A gap's lifecycle state (enhancement plan §17)."""

    OPEN = "open"
    ANSWERED = "answered"
    INVALIDATED = "invalidated"
    STALE = "stale"


def dedup_key(kind: GapKind, *natural_key_parts: str) -> str:
    """Return a stable SHA-256 dedup key for one gap identity.

    ``natural_key_parts`` identifies the concrete, immutable event a gap
    traces back to (a commit SHA; a commit SHA plus a changed path) --
    never a model's wording. Calling this twice with the same ``kind`` and
    parts always returns the same digest, so re-running a producer against
    unchanged history reproduces the same ``gap_id`` (enhancement plan §17:
    "Repeated instances deduplicate by a stable key").
    """
    joined = "\x1f".join((kind.value, *natural_key_parts))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _validate_operator_text(value: str, *, field_name: str) -> str:
    """Cap length and reject credential-shaped text in an operator-facing field.

    Mirrors ``kosha.evidence.model.SourceCoverage._validate_warnings`` and
    ``kosha.connectors.model._validate_diagnostic_text``: ``owner`` and
    ``resolution_reference`` render to a human via ``kosha gap show``/``list``
    exactly like those fields render elsewhere, so they need the same
    enforced guard, not just a documented convention.
    """
    if len(value) > _MAX_OPERATOR_TEXT_CHARS:
        raise ValueError(
            f"{field_name} exceeds {_MAX_OPERATOR_TEXT_CHARS} chars ({len(value)}); "
            "a knowledge-gap field is a short reference, not a source excerpt"
        )
    detectors = scan_text(value)
    if detectors:
        raise ValueError(
            f"{field_name} matched secret detector(s) {sorted(detectors)}; "
            "a knowledge gap may never carry credential-shaped text"
        )
    return value


class KnowledgeGap(BaseModel):
    """One deterministic, auditable knowledge-maintenance insufficiency record.

    Never mutates a claim, concept, or the OKF bundle directly -- a gap is
    pure governance metadata pointing at existing evidence, source runs, and
    concepts. ``resolution_reference`` links to evidence (a digest) or a
    reviewed change (a commit SHA); answering a gap never copies prose into
    the ledger itself (enhancement plan §17).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    gap_id: str
    kind: GapKind
    reason_code: GapReasonCode
    status: GapStatus = GapStatus.OPEN
    opened_at: datetime
    last_seen_at: datetime
    seen_count: int = Field(default=1, ge=1)
    owner: str | None = None
    source_run_ids: tuple[str, ...] = Field(default_factory=tuple)
    evidence_sha256: tuple[str, ...] = Field(default_factory=tuple)
    affected_concept_ids: tuple[str, ...] = Field(default_factory=tuple)
    resolution_reference: str | None = None

    @field_validator("gap_id")
    @classmethod
    def _validate_gap_id(cls, value: str) -> str:
        if not _GAP_ID_RE.fullmatch(value):
            raise ValueError(f"gap_id must be a lowercase 64-hex-char dedup digest, got {value!r}")
        return value

    @field_validator("owner")
    @classmethod
    def _validate_owner(cls, value: str | None) -> str | None:
        return None if value is None else _validate_operator_text(value, field_name="owner")

    @field_validator("resolution_reference")
    @classmethod
    def _validate_resolution_reference(cls, value: str | None) -> str | None:
        return (
            None
            if value is None
            else _validate_operator_text(value, field_name="resolution_reference")
        )

    @model_validator(mode="after")
    def _validate_invariants(self) -> Self:
        if self.last_seen_at < self.opened_at:
            raise ValueError("last_seen_at precedes opened_at")
        requires_resolution = self.status in (GapStatus.ANSWERED, GapStatus.INVALIDATED)
        if requires_resolution and self.resolution_reference is None:
            raise ValueError(
                f"status {self.status.value!r} requires a resolution_reference "
                "linking evidence or a reviewed change"
            )
        if not requires_resolution and self.resolution_reference is not None:
            raise ValueError(
                f"status {self.status.value!r} must not carry a resolution_reference"
            )
        return self

    def observe(
        self,
        *,
        at: datetime,
        source_run_ids: tuple[str, ...],
        evidence_sha256: tuple[str, ...],
        affected_concept_ids: tuple[str, ...],
    ) -> Self:
        """Record a repeated deterministic occurrence of this same gap.

        Bumps ``last_seen_at``/``seen_count`` and unions in any newly seen
        source-run ids, evidence digests, and concept ids -- never changes
        ``status``, even for a terminal gap: the ledger retains stale and
        invalidated history rather than silently reopening it (enhancement
        plan §17: "Stale and invalidated gaps remain auditable").
        """
        if at < self.last_seen_at:
            raise ValueError("observe() cannot move last_seen_at backward")
        return self.model_copy(
            update={
                "last_seen_at": at,
                "seen_count": self.seen_count + 1,
                "source_run_ids": _union(self.source_run_ids, source_run_ids),
                "evidence_sha256": _union(self.evidence_sha256, evidence_sha256),
                "affected_concept_ids": _union(self.affected_concept_ids, affected_concept_ids),
            }
        )

    def answer(self, *, resolution_reference: str, at: datetime) -> Self:
        """Transition an open gap to ``answered``, linking evidence or a reviewed change."""
        return self._resolve(GapStatus.ANSWERED, resolution_reference=resolution_reference, at=at)

    def invalidate(self, *, resolution_reference: str, at: datetime) -> Self:
        """Transition an open gap to ``invalidated`` (reviewed as not a real gap)."""
        return self._resolve(
            GapStatus.INVALIDATED, resolution_reference=resolution_reference, at=at
        )

    def mark_stale(self, *, at: datetime) -> Self:
        """Transition an open gap to ``stale`` (aged out without resolution)."""
        if self.status is not GapStatus.OPEN:
            raise ValueError(
                f"only an open gap may be marked stale, not {self.status.value!r}"
            )
        return self.model_copy(
            update={"status": GapStatus.STALE, "last_seen_at": max(self.last_seen_at, at)}
        )

    def _resolve(self, status: GapStatus, *, resolution_reference: str, at: datetime) -> Self:
        if self.status is not GapStatus.OPEN:
            raise ValueError(
                f"gap {self.gap_id} is already {self.status.value!r}; "
                "a terminal gap is retained for audit, never re-resolved"
            )
        return self.model_copy(
            update={
                "status": status,
                "resolution_reference": resolution_reference,
                "last_seen_at": max(self.last_seen_at, at),
            }
        )


def _union(existing: tuple[str, ...], additions: tuple[str, ...]) -> tuple[str, ...]:
    result = existing
    for value in additions:
        if value not in result:
            result = (*result, value)
    return result
