from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / ".docs" / "s2-v3-preregistration.md"
EVIDENCE_LEDGER = ROOT / ".docs" / "paper" / "evidence-ledger.md"
CITATIONS = ROOT / ".docs" / "paper" / "citations.md"
RELATED_WORK = ROOT / ".docs" / "paper" / "related-work.md"
EXPERIMENTS = ROOT / ".docs" / "paper" / "experiments-and-reproducibility.md"
DRAFT = ROOT / ".docs" / "paper" / "draft.md"

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


_ARXIV_ID = re.compile(r"arXiv:(\d{4}\.\d{4,5})")


def test_related_work_document_exists() -> None:
    assert RELATED_WORK.exists()


def test_every_related_work_citation_is_in_the_inventory() -> None:
    # A citation used in prose but absent from the inventory is exactly the
    # "unchecked citation" the milestone acceptance row forbids.
    citations_text = CITATIONS.read_text("utf-8")
    inventory_ids = set(_ARXIV_ID.findall(citations_text))
    related_work_text = RELATED_WORK.read_text("utf-8")
    used_ids = set(_ARXIV_ID.findall(related_work_text))
    assert used_ids, "related work cites no arXiv identifiers"
    missing = used_ids - inventory_ids
    assert not missing, f"related work cites arXiv ids missing from citations.md: {sorted(missing)}"


def test_experiments_and_reproducibility_document_exists() -> None:
    assert EXPERIMENTS.exists()


def test_draft_document_exists() -> None:
    assert DRAFT.exists()


def test_draft_has_no_banned_claims() -> None:
    # The paper draft lives under .docs/paper/ and is not on the M1 scanner's
    # public-surface list, but it must hold to the same claim-boundary
    # discipline as every scanned doc — the whole point of the milestone.
    from kosha.sync.public_claims import find_banned_claims

    violations = find_banned_claims(DRAFT.read_text("utf-8"))
    assert not violations, f"draft.md has banned claim-boundary violations: {violations}"


def test_draft_carries_required_disclosures() -> None:
    from kosha.sync.public_claims import REQUIRED_DISCLOSURES, normalize_claim_line

    text = "\n".join(normalize_claim_line(line) for line in DRAFT.read_text("utf-8").splitlines())
    for name, pattern in REQUIRED_DISCLOSURES.items():
        if name == "filesystem_not_sandboxed_today":
            continue
        assert pattern.search(text), f"draft.md missing required disclosure: {name}"


def test_draft_links_every_component_document() -> None:
    text = DRAFT.read_text("utf-8")
    for component in (
        ".docs/paper/related-work.md",
        ".docs/paper/experiments-and-reproducibility.md",
        ".docs/paper/evidence-ledger.md",
        ".docs/paper-positioning.md",
    ):
        assert component in text, f"draft.md does not reference component document: {component}"


def test_draft_states_the_s2v3_decision_rule() -> None:
    # The pre-registered decision rule (NO-GO generalizes vs GO pivots to
    # conditional-autonomy framing) must be stated, not silently applied.
    text = DRAFT.read_text("utf-8").lower()
    assert "decision rule" in text
    assert "conditional-autonomy" in text
