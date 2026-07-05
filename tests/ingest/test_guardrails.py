"""Shared ingest guardrail contract tests (PR-1): bounded reads and text guards.

``kosha.ingest.guardrails`` is the single boundary every adapter (folder, url,
and future workspace_export/document adapters) crosses before a ``RawDoc`` is
built: a byte cap enforced during the read, and prompt-injection sanitization
applied to the resulting text. These exercise that shared boundary directly,
the way ``test_url_guardrails.py`` exercises the URL-specific guards.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kosha.ingest.guardrails import (
    IngestGuardrailError,
    IngestPolicy,
    build_raw_doc,
    docs_from_paths,
    guard_text,
    read_bytes_bounded,
    read_text_file_bounded,
)
from kosha.model import Source, SourceKind


def _source(source_id: str = "docs/x.md") -> Source:
    return Source(source_id=source_id, kind=SourceKind.MARKDOWN, location=source_id)


@pytest.mark.parametrize("max_bytes", [0, -1])
def test_ingest_policy_rejects_non_positive_max_bytes(max_bytes: int) -> None:
    with pytest.raises(ValueError, match="max_bytes must be positive"):
        IngestPolicy(max_bytes=max_bytes)


def test_read_bytes_bounded_accepts_a_file_exactly_at_the_cap(tmp_path: Path) -> None:
    path = tmp_path / "at_cap.md"
    path.write_bytes(b"a" * 50)
    result = read_bytes_bounded(path, policy=IngestPolicy(max_bytes=50))
    assert result == b"a" * 50


def test_read_bytes_bounded_fails_loud_one_byte_over_the_cap(tmp_path: Path) -> None:
    path = tmp_path / "over_cap.md"
    path.write_bytes(b"a" * 51)
    with pytest.raises(IngestGuardrailError, match="exceeded max_bytes=50"):
        read_bytes_bounded(path, policy=IngestPolicy(max_bytes=50))


def test_read_text_file_bounded_decodes_utf8_under_the_cap(tmp_path: Path) -> None:
    path = tmp_path / "doc.md"
    path.write_text("héllo wörld", encoding="utf-8")
    text = read_text_file_bounded(path, policy=IngestPolicy(max_bytes=1024))
    assert text == "héllo wörld"


def test_read_text_file_bounded_fails_loud_on_oversized_file(tmp_path: Path) -> None:
    path = tmp_path / "big.md"
    path.write_text("x" * 1000, encoding="utf-8")
    with pytest.raises(IngestGuardrailError) as exc_info:
        read_text_file_bounded(path, policy=IngestPolicy(max_bytes=100))
    message = str(exc_info.value)
    assert "big.md" in message
    assert "max_bytes=100" in message


def test_guard_text_accepts_text_exactly_at_the_cap() -> None:
    text = "x" * 10
    policy = IngestPolicy(max_bytes=10, sanitize_prompt_injection=False)
    result = guard_text(text, source_location="docs/x.md", policy=policy)
    assert result == text


def test_guard_text_fails_loud_when_encoded_text_exceeds_the_cap() -> None:
    with pytest.raises(IngestGuardrailError) as exc_info:
        guard_text("x" * 11, source_location="docs/big.md", policy=IngestPolicy(max_bytes=10))
    message = str(exc_info.value)
    assert "docs/big.md" in message
    assert "max_bytes=10" in message


def test_guard_text_counts_multibyte_characters_by_encoded_length() -> None:
    # Each "e" with an acute accent is 2 UTF-8 bytes; 6 of them is 12 bytes,
    # over a 10-byte cap, even though the string is only 6 *characters* long.
    with pytest.raises(IngestGuardrailError):
        guard_text("é" * 6, source_location="docs/x.md", policy=IngestPolicy(max_bytes=10))


def test_guard_text_strips_hidden_unicode_when_sanitization_is_enabled() -> None:
    poisoned = "visible\u200btext"
    result = guard_text(poisoned, source_location="docs/x.md", policy=IngestPolicy())
    assert result == "visibletext"


def test_guard_text_leaves_hidden_unicode_when_sanitization_is_disabled() -> None:
    poisoned = "visible\u200btext"
    policy = IngestPolicy(sanitize_prompt_injection=False)
    result = guard_text(poisoned, source_location="docs/x.md", policy=policy)
    assert result == poisoned


def test_build_raw_doc_applies_the_shared_text_guard_before_construction() -> None:
    doc = build_raw_doc(source=_source(), text="hello\u200bworld", policy=IngestPolicy())
    assert doc.text == "helloworld"


def test_build_raw_doc_propagates_the_size_guard() -> None:
    with pytest.raises(IngestGuardrailError):
        build_raw_doc(source=_source(), text="x" * 100, policy=IngestPolicy(max_bytes=10))


def test_docs_from_paths_builds_one_doc_per_path_in_order(tmp_path: Path) -> None:
    first = tmp_path / "a.md"
    second = tmp_path / "b.md"
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")

    docs = docs_from_paths(
        [first, second],
        source_for=lambda p: Source(source_id=p.name, kind=SourceKind.MARKDOWN, location=p.name),
    )

    assert [doc.source.source_id for doc in docs] == ["a.md", "b.md"]
    assert [doc.text for doc in docs] == ["first", "second"]


def test_docs_from_paths_fails_loud_on_an_oversized_file(tmp_path: Path) -> None:
    small = tmp_path / "small.md"
    big = tmp_path / "big.md"
    small.write_text("ok", encoding="utf-8")
    big.write_text("x" * 1000, encoding="utf-8")

    with pytest.raises(IngestGuardrailError):
        docs_from_paths(
            [small, big],
            source_for=lambda p: Source(
                source_id=p.name, kind=SourceKind.MARKDOWN, location=p.name
            ),
            policy=IngestPolicy(max_bytes=100),
        )
