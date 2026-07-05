"""Deterministic tests for the local Markdown folder ingest adapter."""

from __future__ import annotations

from pathlib import Path

import pytest

from kosha.ingest import IngestGuardrailError, IngestPolicy, ingest_folder
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


def test_ingest_folder_fails_loud_on_a_file_exceeding_max_bytes(tmp_path: Path) -> None:
    (tmp_path / "big.md").write_text("x" * 1000, encoding="utf-8")
    with pytest.raises(IngestGuardrailError):
        ingest_folder(tmp_path, policy=IngestPolicy(max_bytes=100))


def test_ingest_folder_accepts_a_file_within_a_custom_max_bytes(tmp_path: Path) -> None:
    (tmp_path / "small.md").write_text("well within budget", encoding="utf-8")
    docs = ingest_folder(tmp_path, policy=IngestPolicy(max_bytes=100))
    assert len(docs) == 1
    assert "well within budget" in docs[0].text


def test_ingest_folder_provenance_is_a_stable_relative_path_for_nested_files(
    tmp_path: Path,
) -> None:
    nested = tmp_path / "policies" / "returns"
    nested.mkdir(parents=True)
    (nested / "gold.md").write_text("# Gold\n\nGold members get 45 days.", encoding="utf-8")
    (tmp_path / "top.md").write_text("# Top\n\nTop-level doc.", encoding="utf-8")

    docs = ingest_folder(tmp_path, authority_rank=7)

    by_id = {doc.source.source_id: doc for doc in docs}
    assert set(by_id) == {"policies/returns/gold.md", "top.md"}
    nested_doc = by_id["policies/returns/gold.md"]
    assert nested_doc.source.location == "policies/returns/gold.md"
    assert nested_doc.source.authority_rank == 7
    assert nested_doc.source.kind is SourceKind.MARKDOWN


def test_ingest_folder_provenance_is_independent_of_the_root_absolute_path(
    tmp_path: Path,
) -> None:
    # Two differently-located roots containing the same relative layout must
    # produce identical source_ids -- the property the merge/dedup pipeline
    # relies on to treat the same logical document consistently regardless of
    # where a checkout lives on disk.
    root_a = tmp_path / "checkout_a"
    root_b = tmp_path / "elsewhere" / "checkout_b"
    for root in (root_a, root_b):
        (root / "docs").mkdir(parents=True)
        (root / "docs" / "policy.md").write_text("# Policy\n\nBody.", encoding="utf-8")

    ids_a = [doc.source.source_id for doc in ingest_folder(root_a)]
    ids_b = [doc.source.source_id for doc in ingest_folder(root_b)]
    assert ids_a == ids_b == ["docs/policy.md"]

