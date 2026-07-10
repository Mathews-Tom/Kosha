from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / ".docs" / "s2-v3-preregistration.md"
EVIDENCE_LEDGER = ROOT / ".docs" / "paper" / "evidence-ledger.md"
CITATIONS = ROOT / ".docs" / "paper" / "citations.md"

_TABLE_ROW = re.compile(r"^\|(?P<cells>.+)\|$")


def _table_rows(text: str, *, columns: int) -> list[list[str]]:
    """Parse every Markdown table data row with exactly ``columns`` cells.

    Skips header/separator rows (cells made only of ``-`` and whitespace).
    """
    rows: list[list[str]] = []
    for line in text.splitlines():
        match = _TABLE_ROW.match(line.strip())
        if not match:
            continue
        cells = [cell.strip() for cell in match.group("cells").split("|")]
        if len(cells) != columns:
            continue
        if all(re.fullmatch(r"-+", cell) for cell in cells):
            continue
        if cells == ["Claim", "Value", "Source"] or cells == [
            "Work",
            "Source",
            "Relation to Kosha",
        ]:
            continue
        rows.append(cells)
    return rows


def test_preregistration_document_exists() -> None:
    assert PREREG.exists()


def test_preregistration_covers_required_scope() -> None:
    text = PREREG.read_text("utf-8")
    assert "criteria" in text.lower()
    assert "provider matrix shape" in text.lower()
    assert "case counts" in text.lower()
    assert "go/no-go semantics" in text.lower()
    assert "local-smoke" in text.lower()


def test_evidence_ledger_exists() -> None:
    assert EVIDENCE_LEDGER.exists()


def test_every_evidence_ledger_claim_links_to_a_checked_in_source() -> None:
    # M5: every numeric claim must resolve to a real, checked-in file — a
    # fabricated or stale source path fails the build, not just a lint.
    rows = _table_rows(EVIDENCE_LEDGER.read_text("utf-8"), columns=3)
    assert rows, "evidence ledger has no claim rows"
    for claim, _value, source in rows:
        path = ROOT / source.strip("`")
        assert path.exists(), f"evidence ledger claim {claim!r} cites missing source {source!r}"


def test_citation_inventory_exists() -> None:
    assert CITATIONS.exists()


def test_every_citation_has_a_source_identifier() -> None:
    # No unchecked citation: every row must carry a non-empty identifier
    # (arXiv id, DOI, or named venue), never a bare claim with nothing to
    # verify it against.
    rows = _table_rows(CITATIONS.read_text("utf-8"), columns=3)
    assert rows, "citation inventory has no citation rows"
    for work, source, _relation in rows:
        assert source, f"citation {work!r} has no source identifier"


def test_citation_inventory_covers_required_closest_priors() -> None:
    text = CITATIONS.read_text("utf-8")
    for required in (
        "VMG survey",
        "Zep / Graphiti",
        "MemOS",
        "Approving Automation",
        "Apple Saga",
        "GraphRAG",
        "Retrieval-Augmented Generation",
    ):
        assert required in text, f"citation inventory missing required prior work: {required}"
