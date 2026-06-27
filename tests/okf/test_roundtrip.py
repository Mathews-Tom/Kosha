"""End-to-end M2 acceptance: spec-example fixtures round-trip byte-stable and the
writer conformance guards hold cumulatively over the parse→serialize pipeline."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from kosha.model import IndexDoc, IndexEntry, IndexSection
from kosha.okf import parse_concept, serialize_concept, serialize_index
from kosha.okf.errors import WikilinkError

BUNDLE = Path(__file__).parent / "fixtures" / "acme"
_RESERVED = {"index.md", "log.md"}

CONCEPT_FILES = sorted(p for p in BUNDLE.rglob("*.md") if p.name not in _RESERVED)


def _rel(path: Path) -> str:
    return path.relative_to(BUNDLE).as_posix()


def test_fixtures_present() -> None:
    # Guards against an empty parametrize silently passing.
    assert {_rel(p) for p in CONCEPT_FILES} == {
        "concepts/customer-lifetime-value.md",
        "playbooks/diagnose-revenue-drop.md",
        "tables/orders.md",
    }


@pytest.mark.parametrize("path", CONCEPT_FILES, ids=_rel)
def test_concept_round_trips_byte_stable(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    concept = parse_concept(_rel(path), text)
    assert serialize_concept(concept) == text


def test_unknown_and_extension_keys_survive_round_trip() -> None:
    path = BUNDLE / "concepts" / "customer-lifetime-value.md"
    text = path.read_text(encoding="utf-8")
    concept = parse_concept(_rel(path), text)
    fm = concept.frontmatter
    assert fm.effective_from == datetime(2026, 1, 1, tzinfo=UTC)
    assert fm.effective_to is None
    assert fm.access_level == "internal"
    assert fm.model_extra == {"owner": "analytics-team"}
    assert serialize_concept(concept) == text


def test_concept_id_derived_from_path() -> None:
    path = BUNDLE / "tables" / "orders.md"
    concept = parse_concept(_rel(path), path.read_text(encoding="utf-8"))
    assert concept.concept_id == "tables/orders"
    assert concept.out_links == ["tables/customers", "concepts/customer-lifetime-value"]


def _root_index() -> IndexDoc:
    return IndexDoc(
        okf_version="0.1",
        sections=[
            IndexSection(
                heading="Subdirectories",
                entries=[
                    IndexEntry(
                        title="concepts",
                        target="concepts/index",
                        description="Abstract business ideas and definitions.",
                    ),
                    IndexEntry(
                        title="tables",
                        target="tables/index",
                        description="Source data assets and their schemas.",
                    ),
                    IndexEntry(
                        title="playbooks",
                        target="playbooks/index",
                        description="Triggered, step-by-step processes.",
                    ),
                ],
            )
        ],
    )


def test_root_index_serializes_to_fixture() -> None:
    out = serialize_index(_root_index())
    assert out == (BUNDLE / "index.md").read_text(encoding="utf-8")
    assert "type:" not in out
    assert "](/concepts/index.md)" in out


def test_writer_rejects_wikilink_in_real_concept() -> None:
    path = BUNDLE / "tables" / "orders.md"
    concept = parse_concept(_rel(path), path.read_text(encoding="utf-8"))
    concept.body += "\nSee [[orders]] for more.\n"
    with pytest.raises(WikilinkError):
        serialize_concept(concept)


def test_index_guard_holds_for_non_root() -> None:
    doc = IndexDoc(
        sections=[
            IndexSection(
                heading="Tables",
                entries=[IndexEntry(title="Orders", target="tables/orders")],
            )
        ]
    )
    out = serialize_index(doc)
    assert not out.startswith("---")
    assert "type:" not in out
    assert "[Orders](/tables/orders.md)" in out
