"""Tests for the concept extractor (deterministic boundaries, ≥1 draft)."""

from __future__ import annotations

from pathlib import Path

from kosha.extract import extract_concepts
from kosha.ingest import ingest_folder
from kosha.model import RawDoc, Source, SourceKind
from kosha.providers import ExtractiveGenerationProvider

DOCS = Path(__file__).parent / "fixtures" / "docs"


def _raw(text: str, source_id: str = "mem://doc") -> RawDoc:
    source = Source(source_id=source_id, kind=SourceKind.MARKDOWN, location=source_id)
    return RawDoc(source=source, text=text)


def test_extract_splits_on_headings() -> None:
    returns = ingest_folder(DOCS)[0]  # returns.md has two headings
    drafts = extract_concepts(returns, ExtractiveGenerationProvider())
    titles = [d.title for d in drafts]
    assert titles == ["Returns Policy", "Gold Members"]
    assert "45 days" in drafts[1].body


def test_extract_single_heading_yields_one_draft() -> None:
    shipping = ingest_folder(DOCS)[1]  # shipping.md has one heading
    drafts = extract_concepts(shipping, ExtractiveGenerationProvider())
    assert len(drafts) == 1
    assert drafts[0].title == "Shipping"


def test_extract_no_heading_yields_one_draft_with_fallback_title() -> None:
    raw = _raw("Just a sentence with no heading at all.", source_id="docs/loose.md")
    drafts = extract_concepts(raw, ExtractiveGenerationProvider())
    assert len(drafts) == 1
    assert drafts[0].title == "docs/loose.md"
    assert drafts[0].source_id == "docs/loose.md"


def test_extract_always_returns_at_least_one_draft() -> None:
    drafts = extract_concepts(_raw(""), ExtractiveGenerationProvider())
    assert len(drafts) == 1


def test_extract_drafts_carry_type_and_description() -> None:
    drafts = extract_concepts(
        _raw("# Refunds\nApproved refunds settle in 5-7 business days."),
        ExtractiveGenerationProvider(),
    )
    draft = drafts[0]
    assert draft.type == "concept"
    assert draft.description
    assert "business days" in draft.description


def test_extract_is_deterministic() -> None:
    raw = ingest_folder(DOCS)[0]
    provider = ExtractiveGenerationProvider()
    assert extract_concepts(raw, provider) == extract_concepts(raw, provider)


def test_extract_preamble_folds_into_first_section() -> None:
    raw = _raw("Intro line.\n# Heading\nBody line.")
    drafts = extract_concepts(raw, ExtractiveGenerationProvider())
    assert len(drafts) == 1
    assert "Intro line." in drafts[0].body
    assert "Body line." in drafts[0].body
