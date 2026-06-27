"""Deterministic tests for the local Markdown folder ingest adapter."""

from __future__ import annotations

from pathlib import Path

import pytest

from kosha.ingest import ingest_folder
from kosha.model import SourceKind

DOCS = Path(__file__).parent / "fixtures" / "docs"


def test_ingest_folder_reads_every_markdown_file_sorted() -> None:
    docs = ingest_folder(DOCS)
    ids = [doc.source.source_id for doc in docs]
    assert ids == ["returns.md", "shipping.md"]


def test_ingest_folder_sets_relative_ids_and_markdown_kind() -> None:
    docs = ingest_folder(DOCS, authority_rank=4)
    returns = docs[0]
    assert returns.source.kind is SourceKind.MARKDOWN
    assert returns.source.location == "returns.md"
    assert returns.source.authority_rank == 4
    assert returns.source.title == "Returns Policy"
    assert "30 days" in returns.text


def test_ingest_folder_title_falls_back_to_stem() -> None:
    docs = ingest_folder(DOCS)
    shipping = docs[1]
    # First line is a heading, so the title comes from it, not the stem.
    assert shipping.source.title == "Shipping"


def test_ingest_folder_is_deterministic() -> None:
    assert ingest_folder(DOCS) == ingest_folder(DOCS)


def test_ingest_folder_rejects_a_file_path() -> None:
    with pytest.raises(NotADirectoryError):
        ingest_folder(DOCS / "returns.md")
