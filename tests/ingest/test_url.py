"""Deterministic tests for the URL ingest adapter (``parse_html``)."""

from __future__ import annotations

from pathlib import Path

from kosha.ingest import parse_html
from kosha.model import SourceKind

FIXTURE = Path(__file__).parent / "fixtures" / "page.html"
URL = "https://example.com/returns"


def test_parse_html_drops_script_and_style() -> None:
    doc = parse_html(FIXTURE.read_text(encoding="utf-8"), url=URL)
    assert "should not appear" not in doc.text
    assert "color: red" not in doc.text


def test_parse_html_converts_headings_to_markdown() -> None:
    doc = parse_html(FIXTURE.read_text(encoding="utf-8"), url=URL)
    assert "# Returns Policy" in doc.text
    assert "## Gold Members" in doc.text
    assert "45 days" in doc.text


def test_parse_html_captures_title_and_source_metadata() -> None:
    doc = parse_html(FIXTURE.read_text(encoding="utf-8"), url=URL, authority_rank=3)
    assert doc.source.kind is SourceKind.URL
    assert doc.source.source_id == URL
    assert doc.source.location == URL
    assert doc.source.title == "Northwind Returns Policy"
    assert doc.source.authority_rank == 3


def test_parse_html_is_deterministic() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    assert parse_html(html, url=URL) == parse_html(html, url=URL)


def test_parse_html_normalizes_whitespace() -> None:
    doc = parse_html("<p>  a   b  </p>\n\n<p>c</p>", url=URL)
    assert doc.text == "a b\nc"
