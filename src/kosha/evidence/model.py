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

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from kosha.evidence.paths import validate_digest, validate_run_id


class RunStatus(StrEnum):
    """Outcome of one source-run's ingest attempt."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FAILED = "failed"


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
    """One deterministic, immutable manifest of a single ingest attempt against a source."""

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
