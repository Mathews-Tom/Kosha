"""Deterministic, immutable evidence contracts for the private content-addressed vault.

`EvidenceDocument` records exactly what crossed the model-facing extraction
boundary for one piece of source content; `SourceRun` is the immutable
manifest of one ingest attempt against a source, referencing zero or more
`EvidenceDocument` records in the order they were produced.

A non-accepted run (`rejected` or `failed`) MUST NOT carry any evidence: the
source body never enters a rejected manifest, only the detector names and
non-secret warnings that explain the rejection (DEVELOPMENT_PLAN.md M2;
enhancement plan §9).
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from kosha.evidence.paths import validate_digest, validate_run_id
from kosha.security.secret_scan import scan_text


def hash_evidence_text(text: str) -> str:
    """Return the SHA-256 digest of ``text``'s exact UTF-8 bytes.

    This is the one formula every evidence-producing surface must use: the
    ingest boundary (to stamp a :class:`~kosha.model.RawDoc`/``Claim`` before
    extraction), the private store (to address the object it writes), and a
    later verifier (to confirm stored bytes still match). Computing it here
    needs no filesystem access, so a caller can bind evidence identity to a
    document before ever deciding whether that identity becomes durable.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class RunStatus(StrEnum):
    """Outcome of one source-run's ingest attempt."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FAILED = "failed"


class CoverageKind(StrEnum):
    """How much of a source a run actually observed (DEVELOPMENT_PLAN.md M5).

    Authority (:attr:`~kosha.model.Source.authority_rank`) answers which source
    wins when assertions conflict; coverage answers what portion of that
    source this run observed. The two are never combined into one field or
    policy -- overloading authority with completeness would let a merely
    partial retrieval outrank a source it never fully saw.
    """

    COMPLETE = "complete"
    WINDOWED = "windowed"
    CURSOR_INCREMENTAL = "cursor_incremental"
    SAMPLED = "sampled"
    BEST_EFFORT = "best_effort"
    UNKNOWN = "unknown"


class SourceCoverage(BaseModel):
    """What portion of a source one :class:`SourceRun` observed.

    Defaults to :attr:`CoverageKind.UNKNOWN` -- a caller that cannot establish
    completeness must say so explicitly rather than have this model infer
    ``complete`` by omission. ``scope`` is the human-readable statement of what
    was actually covered (a traversal root and suffix, a single file snapshot,
    a fetched response body); the window/cursor/limit fields describe a
    bounded or incremental run, populated only by adapters that support them.
    ``truncated``/``permission_limited`` flag a bounded fallback, which can
    never coexist with ``complete`` -- that combination would assert
    exhaustive coverage of a run that is, by its own metadata, cut short.

    ``warnings`` is validated, not merely a documented convention: each entry
    is scanned with the same detector :func:`kosha.security.secret_scan.scan_text`
    uses for source text, and rejected -- naming only the detector, never the
    match -- if it looks credential-shaped, and capped in length so a warning
    cannot become a vehicle for pasting a source excerpt.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: CoverageKind = CoverageKind.UNKNOWN
    scope: str | None = None
    requested_window_start: datetime | None = None
    requested_window_end: datetime | None = None
    observed_window_start: datetime | None = None
    observed_window_end: datetime | None = None
    cursor_before: str | None = None
    cursor_after: str | None = None
    configured_item_limit: int | None = Field(default=None, ge=0)
    observed_item_count: int | None = Field(default=None, ge=0)
    truncated: bool = False
    permission_limited: bool = False
    warnings: tuple[str, ...] = Field(default_factory=tuple)

    @field_validator("warnings")
    @classmethod
    def _validate_warnings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for warning in value:
            if len(warning) > 500:
                raise ValueError(
                    f"coverage warning exceeds 500 chars ({len(warning)}); "
                    "a warning is a short note, not a source excerpt"
                )
            detectors = scan_text(warning)
            if detectors:
                raise ValueError(
                    f"coverage warning matched secret detector(s) {sorted(detectors)}; "
                    "warnings may never carry credential-shaped text"
                )
        return value

    @model_validator(mode="after")
    def _validate_invariants(self) -> Self:
        if self.truncated and self.kind is CoverageKind.COMPLETE:
            raise ValueError("a truncated run cannot declare complete coverage")
        if self.permission_limited and self.kind is CoverageKind.COMPLETE:
            raise ValueError("a permission-limited run cannot declare complete coverage")
        windows = (
            (self.requested_window_start, self.requested_window_end, "requested"),
            (self.observed_window_start, self.observed_window_end, "observed"),
        )
        for start, end, label in windows:
            if start is not None and end is not None and end < start:
                raise ValueError(f"{label} window end precedes its start")
        return self


class EvidenceDocument(BaseModel):
    """One immutable, content-addressed record of exact normalized model-facing text.

    ``sha256`` is the digest of the exact UTF-8 normalized text extraction
    receives -- not the original remote bytes -- so the hash proves what the
    model actually saw.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    sha256: str
    source_id: str
    location: str
    retrieved_at: datetime | None = None
    media_type: str
    normalized_text_bytes: int = Field(ge=0)
    normalization_version: str

    @field_validator("sha256")
    @classmethod
    def _validate_sha256(cls, value: str) -> str:
        return validate_digest(value)


class SourceRun(BaseModel):
    """One deterministic, immutable manifest of a single ingest attempt against a source.

    ``coverage`` states what portion of the source this run actually observed
    (DEVELOPMENT_PLAN.md M5) -- a field wholly separate from authority: this
    manifest carries no ``authority_rank`` of its own, only the completeness
    classification a reviewer or audit consumer needs beside the source's
    already-recorded authority. It defaults to :attr:`CoverageKind.UNKNOWN`
    exactly like :class:`SourceCoverage` itself, so a legacy pre-M5 manifest
    loaded from disk (with no ``coverage`` key) reports honestly that its
    completeness was never established, rather than being silently upgraded
    to ``complete``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    bundle_identity: str
    source_instance_id: str
    adapter: str
    adapter_version: str
    started_at: datetime
    completed_at: datetime
    status: RunStatus
    evidence: tuple[EvidenceDocument, ...] = Field(default_factory=tuple)
    detector_names: tuple[str, ...] = Field(default_factory=tuple)
    warnings: tuple[str, ...] = Field(default_factory=tuple)
    coverage: SourceCoverage = Field(default_factory=SourceCoverage)

    @field_validator("run_id")
    @classmethod
    def _validate_run_id(cls, value: str) -> str:
        return validate_run_id(value)

    @model_validator(mode="after")
    def _validate_invariants(self) -> Self:
        if self.status is not RunStatus.ACCEPTED and self.evidence:
            raise ValueError(
                f"{self.status.value} run {self.run_id!r} must not retain a source body"
            )
        if self.completed_at < self.started_at:
            raise ValueError(f"run {self.run_id!r} completed before it started")
        return self


def source_run_to_json(run: SourceRun) -> dict[str, object]:
    """Return the stable, byte-reproducible JSON object written for ``run``."""
    return run.model_dump(mode="json")


def source_run_from_json(raw: object) -> SourceRun:
    """Build a :class:`SourceRun` from a decoded JSON manifest, failing loud on drift."""
    if not isinstance(raw, dict):
        raise TypeError("source-run manifest must be a JSON object")
    return SourceRun.model_validate(raw)
