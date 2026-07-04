"""Structured telemetry events for benchmark and pipeline decisions.

Telemetry is opt-in and in-memory by default. Event payloads are deliberately
small: routing, provider accounting, and decisions only. Source bodies, prompt
text, generated text, and retrieved context are rejected so observability cannot
leak corpus content.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

_BODY_FIELD_NAMES = frozenset(
    {
        "body",
        "source_body",
        "source_text",
        "raw_body",
        "raw_text",
        "context",
        "prompt",
        "completion",
        "generation",
        "generated_text",
        "text",
    }
)

TelemetryKind = Literal["route", "decision", "provider"]


class TelemetrySink(Protocol):
    """Receives sanitized telemetry records."""

    def emit(self, record: dict[str, object]) -> None:
        """Store or forward one telemetry record."""
        ...


@dataclass(frozen=True)
class TokenCost:
    """Token and optional cost accounting for a provider call."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None

    def to_record(self) -> dict[str, object]:
        total = self.prompt_tokens + self.completion_tokens
        record: dict[str, object] = {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens if self.total_tokens is not None else total,
        }
        if self.estimated_cost_usd is not None:
            record["estimated_cost_usd"] = self.estimated_cost_usd
        return record


@dataclass(frozen=True)
class TelemetryEvent:
    """One sanitized event emitted by a decision or provider surface."""

    kind: TelemetryKind
    surface: str
    fields: dict[str, object] = field(default_factory=dict)

    def to_record(self) -> dict[str, object]:
        _reject_body_fields(self.fields)
        record: dict[str, object] = {"kind": self.kind, "surface": self.surface}
        record.update(self.fields)
        _reject_body_fields(record)
        return record


@dataclass
class InMemoryTelemetrySink:
    """Small test and benchmark sink retaining sanitized event records."""

    records: list[dict[str, object]] = field(default_factory=list)

    def emit(self, record: dict[str, object]) -> None:
        _reject_body_fields(record)
        self.records.append(dict(record))


class NullTelemetrySink:
    """Telemetry sink that intentionally drops events."""

    def emit(self, record: dict[str, object]) -> None:
        _reject_body_fields(record)


NULL_TELEMETRY = NullTelemetrySink()


def emit_route(
    sink: TelemetrySink | None,
    *,
    surface: str,
    lane: str,
    confidence: float,
    provider_name: str | None = None,
) -> None:
    """Record a routing lane and confidence without source content."""
    fields: dict[str, object] = {"lane": lane, "confidence": confidence}
    if provider_name is not None:
        fields["provider_name"] = provider_name
    _emit(sink, TelemetryEvent(kind="route", surface=surface, fields=fields))


def emit_decision(
    sink: TelemetrySink | None,
    *,
    surface: str,
    outcome: str,
    confidence: float | None = None,
    lane: str | None = None,
    provider_name: str | None = None,
) -> None:
    """Record a decision outcome and optional routing context."""
    fields: dict[str, object] = {"outcome": outcome}
    if confidence is not None:
        fields["confidence"] = confidence
    if lane is not None:
        fields["lane"] = lane
    if provider_name is not None:
        fields["provider_name"] = provider_name
    _emit(sink, TelemetryEvent(kind="decision", surface=surface, fields=fields))


def emit_provider_call(
    sink: TelemetrySink | None,
    *,
    surface: str,
    provider_name: str,
    usage: TokenCost | None = None,
) -> None:
    """Record provider identity plus token and cost fields when available."""
    fields: dict[str, object] = {"provider_name": provider_name}
    if usage is not None:
        fields.update(usage.to_record())
    _emit(sink, TelemetryEvent(kind="provider", surface=surface, fields=fields))


def _emit(sink: TelemetrySink | None, event: TelemetryEvent) -> None:
    target = sink or NULL_TELEMETRY
    target.emit(event.to_record())


def _reject_body_fields(record: dict[str, object]) -> None:
    forbidden = _BODY_FIELD_NAMES & record.keys()
    if forbidden:
        names = ", ".join(sorted(forbidden))
        raise ValueError(f"telemetry record includes source-body field(s): {names}")


__all__ = [
    "NULL_TELEMETRY",
    "InMemoryTelemetrySink",
    "NullTelemetrySink",
    "TelemetryEvent",
    "TelemetryKind",
    "TelemetrySink",
    "TokenCost",
    "emit_decision",
    "emit_provider_call",
    "emit_route",
]
