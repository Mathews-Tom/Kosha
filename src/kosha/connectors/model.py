"""Deterministic, explicit-registry connector contracts (DEVELOPMENT_PLAN.md M6).

``ConnectorDefinition`` is one shipped, hand-registered connector -- never a
dynamic plugin -- wiring an existing ingest adapter through the ordinary
plan -> approve -> commit gate. ``SourceInstance`` is an operator's
repeatable, non-secret configuration of one connector. ``ConnectorState`` is
that instance's durable, mutable cursor state, wholly separate from the
immutable evidence vault (DEVELOPMENT_PLAN.md M2): it carries no source body
text and advances only after a run's evidence has actually been persisted
(enhancement plan §13).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from kosha.approve import Reader
from kosha.evidence import EvidenceStore
from kosha.evidence.paths import validate_run_id
from kosha.pipeline import IngestResult
from kosha.security.secret_scan import scan_text

_MAX_DIAGNOSTIC_CHARS = 500
_MAX_RECENT_RUNS = 20
_CURRENT_STATE_SCHEMA_VERSION = 1


class ConnectorBackend(StrEnum):
    """Which ingest surface a shipped connector wires.

    ``FOLDER``/``URL`` wire an existing ``kosha.ingest`` adapter; ``GIT``/
    ``MCP`` (DEVELOPMENT_PLAN.md M7) are dedicated connector-owned surfaces
    with no separate ``kosha.ingest`` adapter of their own.
    """

    FOLDER = "folder"
    URL = "url"
    GIT = "git"
    MCP = "mcp"


class SourceRunOutcome(StrEnum):
    """Outcome of one connector run attempt, as the state orchestrator sees it.

    Distinct from :class:`kosha.evidence.RunStatus`, which describes the
    evidence manifest itself: a run can produce ``RunStatus.ACCEPTED``
    evidence and still land here as :attr:`REJECTED` (a human declined the
    resulting plan, or the plan was empty), never reaching
    ``persist_evidence_run``. Only :attr:`SUCCESS` -- a committed,
    non-dry-run run whose evidence was actually persisted -- ever advances a
    cursor.
    """

    SUCCESS = "success"
    REJECTED = "rejected"
    FAILED = "failed"


def _validate_diagnostic_text(value: str, *, field_name: str) -> str:
    """Cap length and reject credential-shaped text in an operator-facing field.

    Mirrors ``kosha.evidence.model.SourceCoverage._validate_warnings``: a
    connector's config and run diagnostics render to a human via ``kosha
    source list/run/status`` exactly like coverage warnings render via
    ``kosha evidence show``, so they need the same enforced guard, not just a
    documented convention.
    """
    if len(value) > _MAX_DIAGNOSTIC_CHARS:
        raise ValueError(
            f"{field_name} exceeds {_MAX_DIAGNOSTIC_CHARS} chars ({len(value)}); "
            "a diagnostic value is a short note, not a source excerpt"
        )
    detectors = scan_text(value)
    if detectors:
        raise ValueError(
            f"{field_name} matched secret detector(s) {sorted(detectors)}; "
            "connector config/diagnostics may never carry credential-shaped text"
        )
    return value


class SourceInstance(BaseModel):
    """One operator-configured, repeatable source (DEVELOPMENT_PLAN.md M6).

    ``config`` holds only non-secret values -- typically a connector's plain
    parameters (a folder path, a URL) or the *names* of environment
    variables a future connector should resolve at run time, never a
    resolved secret value itself. Every key/value pair is scanned the same
    way :class:`~kosha.evidence.model.SourceCoverage` warnings are, so a
    credential pasted here fails loud at load time instead of silently
    reaching ``kosha source list``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    instance_id: str
    connector_id: str
    config: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True
    schedule: str | None = None

    @field_validator("instance_id")
    @classmethod
    def _validate_instance_id(cls, value: str) -> str:
        return validate_run_id(value)

    @field_validator("connector_id")
    @classmethod
    def _validate_connector_id(cls, value: str) -> str:
        if not value:
            raise ValueError("connector_id must not be empty")
        return value

    @field_validator("config")
    @classmethod
    def _validate_config(cls, value: dict[str, str]) -> dict[str, str]:
        for key, entry in value.items():
            if not key:
                raise ValueError("config key must not be empty")
            _validate_diagnostic_text(f"{key}={entry}", field_name=f"config[{key!r}]")
        return value


class RunSummary(BaseModel):
    """One bounded, non-secret record of a past connector run attempt."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    status: SourceRunOutcome
    started_at: datetime
    completed_at: datetime
    message: str = ""

    @field_validator("message")
    @classmethod
    def _validate_message(cls, value: str) -> str:
        return _validate_diagnostic_text(value, field_name="run summary message")

    @model_validator(mode="after")
    def _validate_invariants(self) -> Self:
        if self.completed_at < self.started_at:
            raise ValueError(f"run {self.run_id!r} completed before it started")
        return self


class ConnectorState(BaseModel):
    """Durable, mutable cursor state for one source instance.

    Wholly separate from the immutable evidence vault: this file only ever
    records where a connector's next run should resume and a bounded history
    of recent attempts. It carries no source body text and is never
    content-addressed. ``advance``/``record_attempt`` are the only ways to
    derive a new state, so the "cursor only moves on success" invariant is
    enforced in one place rather than at every call site.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = _CURRENT_STATE_SCHEMA_VERSION
    instance_id: str
    cursor: str | None = None
    last_success_run_id: str | None = None
    last_success_at: datetime | None = None
    recent_runs: tuple[RunSummary, ...] = Field(default_factory=tuple)

    @field_validator("instance_id")
    @classmethod
    def _validate_instance_id(cls, value: str) -> str:
        return validate_run_id(value)

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: int) -> int:
        if value != _CURRENT_STATE_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported connector state schema_version {value}; "
                f"expected {_CURRENT_STATE_SCHEMA_VERSION}"
            )
        return value

    def advance(self, summary: RunSummary, *, cursor: str | None) -> Self:
        """Return new state recording a SUCCESSFUL run and the advanced cursor."""
        if summary.status is not SourceRunOutcome.SUCCESS:
            raise ValueError("advance() requires a SUCCESS run summary")
        return self.model_copy(
            update={
                "recent_runs": (*self.recent_runs, summary)[-_MAX_RECENT_RUNS:],
                "last_success_run_id": summary.run_id,
                "last_success_at": summary.completed_at,
                "cursor": cursor,
            }
        )

    def record_attempt(self, summary: RunSummary) -> Self:
        """Return new state recording a FAILED/REJECTED run; cursor untouched."""
        if summary.status is SourceRunOutcome.SUCCESS:
            raise ValueError(
                "record_attempt() must not be used for a SUCCESS run summary; use advance()"
            )
        recent = (*self.recent_runs, summary)[-_MAX_RECENT_RUNS:]
        return self.model_copy(update={"recent_runs": recent})


@dataclass(frozen=True)
class ConnectorRunContext:
    """Everything a connector's ingest function needs for one run attempt."""

    instance: SourceInstance
    bundle_root: Path
    asof: datetime
    cursor: str | None
    evidence_store: EvidenceStore
    dry_run: bool
    assume_yes: bool
    reviewer: str | None
    reader: Reader | None


ConnectorIngestFn = Callable[[ConnectorRunContext], IngestResult]


@dataclass(frozen=True)
class ConnectorDefinition:
    """One shipped connector: an explicit registry entry, never a dynamic plugin."""

    connector_id: str
    display_name: str
    backend: ConnectorBackend
    ingest: ConnectorIngestFn
    required_config_keys: tuple[str, ...] = ()
    required_env_vars: tuple[str, ...] = ()
    supports_cursor: bool = False
