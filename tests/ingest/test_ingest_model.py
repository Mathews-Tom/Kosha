"""Tests for the ingest-layer data model (``Source`` / ``RawDoc``)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from kosha.model import RawDoc, Source, SourceKind


def test_source_kind_values() -> None:
    assert SourceKind.URL == "url"
    assert SourceKind.MARKDOWN == "markdown"


def test_source_defaults_authority_rank_to_zero() -> None:
    source = Source(
        source_id="https://example.com/policy",
        kind=SourceKind.URL,
        location="https://example.com/policy",
    )
    assert source.authority_rank == 0
    assert source.title is None
    assert source.retrieved_at is None


def test_source_carries_authority_rank_and_metadata() -> None:
    when = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    source = Source(
        source_id="docs/returns.md",
        kind=SourceKind.MARKDOWN,
        location="docs/returns.md",
        title="Returns",
        authority_rank=5,
        retrieved_at=when,
    )
    assert source.authority_rank == 5
    assert source.title == "Returns"
    assert source.retrieved_at == when


def test_source_kind_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        Source(source_id="x", kind="ftp", location="x")  # type: ignore[arg-type]


def test_rawdoc_binds_text_to_source() -> None:
    source = Source(
        source_id="docs/shipping.md",
        kind=SourceKind.MARKDOWN,
        location="docs/shipping.md",
    )
    doc = RawDoc(source=source, text="Standard shipping takes 3-5 business days.")
    assert doc.source.source_id == "docs/shipping.md"
    assert "3-5" in doc.text


def test_rawdoc_round_trips_through_pydantic() -> None:
    source = Source(
        source_id="https://example.com/a",
        kind=SourceKind.URL,
        location="https://example.com/a",
        authority_rank=2,
    )
    doc = RawDoc(source=source, text="hello")
    restored = RawDoc.model_validate(doc.model_dump())
    assert restored == doc
