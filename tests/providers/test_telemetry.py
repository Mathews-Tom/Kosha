"""Structured telemetry event shape tests."""

from __future__ import annotations

import pytest

from kosha.telemetry import (
    InMemoryTelemetrySink,
    TelemetryEvent,
    TokenCost,
    emit_decision,
    emit_provider_call,
    emit_route,
)


def test_route_event_records_lane_confidence_and_provider() -> None:
    sink = InMemoryTelemetrySink()

    emit_route(
        sink,
        surface="pipeline.ingest",
        lane="auto",
        confidence=0.97,
        provider_name="lexical-hash-256",
    )

    assert sink.records == [
        {
            "kind": "route",
            "surface": "pipeline.ingest",
            "lane": "auto",
            "confidence": 0.97,
            "provider_name": "lexical-hash-256",
        }
    ]


def test_decision_event_records_outcome_without_body_text() -> None:
    sink = InMemoryTelemetrySink()

    emit_decision(
        sink,
        surface="dedup.resolve",
        outcome="UPDATE",
        confidence=0.5,
        lane="skim",
        provider_name="extractive",
    )

    assert sink.records[0] == {
        "kind": "decision",
        "surface": "dedup.resolve",
        "outcome": "UPDATE",
        "confidence": 0.5,
        "lane": "skim",
        "provider_name": "extractive",
    }
    assert "body" not in sink.records[0]
    assert "text" not in sink.records[0]


def test_provider_event_records_tokens_and_optional_cost() -> None:
    sink = InMemoryTelemetrySink()

    emit_provider_call(
        sink,
        surface="bench.answer",
        provider_name="extractive",
        usage=TokenCost(prompt_tokens=12, completion_tokens=3, estimated_cost_usd=0.0015),
    )

    assert sink.records == [
        {
            "kind": "provider",
            "surface": "bench.answer",
            "provider_name": "extractive",
            "prompt_tokens": 12,
            "completion_tokens": 3,
            "total_tokens": 15,
            "estimated_cost_usd": 0.0015,
        }
    ]


def test_telemetry_rejects_source_body_fields() -> None:
    event = TelemetryEvent(kind="decision", surface="pipeline", fields={"source_body": "secret"})

    with pytest.raises(ValueError, match="source-body"):
        event.to_record()


def test_sink_rejects_raw_text_fields_from_custom_emitters() -> None:
    sink = InMemoryTelemetrySink()

    with pytest.raises(ValueError, match="source-body"):
        sink.emit({"kind": "provider", "surface": "bench", "prompt": "full source"})
