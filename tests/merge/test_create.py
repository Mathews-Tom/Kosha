"""CREATE path: claim-projected concept written via M2 guards (M7 PR-2)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from kosha.extract import ConceptDraft
from kosha.merge import claims_from_draft, create_concept, segment_statements, write_concept
from kosha.model import ClaimStatus, Source, SourceKind
from kosha.okf import load_bundle
from kosha.okf.errors import WikilinkError
from kosha.validate import validate_bundle

_T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _source(source_id: str = "s1", title: str | None = "Returns Policy") -> Source:
    return Source(
        source_id=source_id,
        kind=SourceKind.MARKDOWN,
        location=f"file://{source_id}.md",
        title=title,
    )


def _draft(body: str, *, type_: str = "policy") -> ConceptDraft:
    return ConceptDraft(
        title="Returns",
        body=body,
        description="How returns are handled.",
        type=type_,
        source_id="s1",
    )


def test_segment_statements_splits_paragraphs_and_skips_citations() -> None:
    body = "First claim.\n\nSecond claim.\n\n# Citations\n[1] file://x"
    assert segment_statements(body) == ["First claim.", "Second claim."]


def test_claims_from_draft_stamps_source_provenance() -> None:
    draft = _draft("Returns within 30 days.\n\nGold members ship free.")
    claims = claims_from_draft(draft, _source(), _T0)
    assert [c.statement for c in claims] == ["Returns within 30 days.", "Gold members ship free."]
    assert all(c.source_id == "s1" for c in claims)
    assert all(c.status is ClaimStatus.CURRENT for c in claims)
    assert claims[0].citations == ["Returns Policy (file://s1.md)"]


def test_claims_from_draft_falls_back_to_description_when_body_empty() -> None:
    claims = claims_from_draft(_draft(""), _source(), _T0)
    assert len(claims) == 1
    assert claims[0].statement == "How returns are handled."


def test_create_concept_projects_body_from_claims() -> None:
    draft = _draft("Returns within 30 days.\n\nGold members ship free.")
    concept = create_concept(draft, "policies/returns", _source(), _T0)
    assert concept.concept_id == "policies/returns"
    assert concept.frontmatter.type == "policy"
    assert concept.frontmatter.timestamp == _T0
    assert "Returns within 30 days." in concept.body
    assert "Gold members ship free." in concept.body
    assert "# Citations" in concept.body
    assert len(concept.claims) == 2


def test_write_concept_produces_a_conformant_bundle(tmp_path: Path) -> None:
    draft = _draft("Returns within 30 days.\n\nGold members ship free.")
    concept = create_concept(draft, "policies/returns", _source(), _T0)
    path = write_concept(tmp_path, concept)
    assert path == tmp_path / "policies" / "returns.md"
    assert path.is_file()

    report = validate_bundle(tmp_path)
    assert report.ok
    assert report.errors == []

    # The written file round-trips back through the parser with its type intact.
    reloaded = load_bundle(tmp_path)
    assert reloaded.concepts["policies/returns"].frontmatter.type == "policy"


def test_write_concept_enforces_the_wikilink_guard(tmp_path: Path) -> None:
    draft = _draft("See [[Other Concept]] for details.")
    concept = create_concept(draft, "policies/returns", _source(), _T0)
    with pytest.raises(WikilinkError):
        write_concept(tmp_path, concept)
