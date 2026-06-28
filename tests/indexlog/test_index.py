"""Per-directory index.md regeneration (M8 PR-3)."""

from __future__ import annotations

from pathlib import Path

from kosha.indexlog import (
    bundle_directories,
    directory_of,
    regenerate_index,
    regenerate_indexes,
    write_indexes,
)
from kosha.model import Bundle, Concept, Frontmatter
from kosha.okf.serialize import serialize_concept
from kosha.validate import validate_bundle


def _concept(concept_id: str, *, title: str, description: str) -> Concept:
    return Concept(
        concept_id=concept_id,
        frontmatter=Frontmatter(type="Concept", title=title, description=description),
        body=f"\n# {title}\n\n{description}\n",
    )


def _bundle(*concepts: Concept, root_path: str = "bundles/demo") -> Bundle:
    return Bundle(root_path=root_path, concepts={c.concept_id: c for c in concepts})


_SHIPPING = _concept("policies/shipping", title="Shipping", description="Delivery timelines.")
_REFUNDS = _concept("policies/refunds", title="Refunds", description="How refunds are issued.")
_STANDARD = _concept(
    "policies/returns/standard", title="Standard Window", description="30-day returns."
)


def test_directory_of_and_bundle_directories() -> None:
    bundle = _bundle(_SHIPPING, _STANDARD)
    assert directory_of("policies/shipping") == "policies"
    assert directory_of("root-level") == ""
    assert bundle_directories(bundle) == ["", "policies", "policies/returns"]


def test_regenerate_index_lists_direct_concepts_with_descriptions() -> None:
    index = regenerate_index(_bundle(_SHIPPING, _REFUNDS), "policies")
    assert index.okf_version is None  # non-root: no frontmatter
    [section] = index.sections
    assert section.heading == "Policies"
    targets = {entry.target: entry.description for entry in section.entries}
    assert targets == {
        "policies/refunds": "How refunds are issued.",
        "policies/shipping": "Delivery timelines.",
    }


def test_subdirectories_are_listed_before_concepts_and_link_their_index() -> None:
    index = regenerate_index(_bundle(_SHIPPING, _STANDARD), "policies")
    [section] = index.sections
    # The "returns" subdirectory links its own index.md and sorts ahead of concepts.
    assert section.entries[0].target == "policies/returns/index"
    assert section.entries[0].title == "Returns"
    assert section.entries[-1].target == "policies/shipping"


def test_root_index_carries_okf_version() -> None:
    index = regenerate_index(_bundle(_SHIPPING), "")
    assert index.okf_version == "0.1"
    assert index.sections[0].heading == "Demo"


def test_regenerate_indexes_covers_every_directory() -> None:
    indexes = regenerate_indexes(_bundle(_SHIPPING, _STANDARD))
    assert set(indexes) == {"index.md", "policies/index.md", "policies/returns/index.md"}
    # Non-root index never emits frontmatter; bundle-relative links only.
    assert not indexes["policies/index.md"].startswith("---")
    assert "[[" not in indexes["policies/index.md"]
    assert "(/policies/shipping.md)" in indexes["policies/index.md"]


def test_regenerate_indexes_is_deterministic() -> None:
    bundle = _bundle(_SHIPPING, _REFUNDS, _STANDARD)
    assert regenerate_indexes(bundle) == regenerate_indexes(bundle)


def test_root_index_serializes_only_okf_version_frontmatter() -> None:
    root = regenerate_indexes(_bundle(_SHIPPING))["index.md"]
    assert root.startswith("---\nokf_version: '0.1'\n---\n")
    assert "type:" not in root


def test_written_indexes_make_a_conformant_bundle(tmp_path: Path) -> None:
    bundle = _bundle(_SHIPPING, _REFUNDS, _STANDARD, root_path=str(tmp_path))
    # The concepts must exist on disk for links to resolve.
    for concept in bundle.concepts.values():
        path = tmp_path / f"{concept.concept_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(serialize_concept(concept), encoding="utf-8")

    written = write_indexes(tmp_path, bundle)
    assert len(written) == 3

    report = validate_bundle(tmp_path)
    assert report.ok
    assert report.errors == []
    assert report.warnings == []
