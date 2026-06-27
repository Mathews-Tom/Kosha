"""Path validation for the cross-linker (M8 PR-1)."""

from __future__ import annotations

from kosha.link import (
    ResolvedLink,
    bundle_relative_link,
    classify_link,
    dangling_links,
    is_bundle_relative,
)
from kosha.model import Bundle, Concept, Frontmatter


def _concept(concept_id: str, body: str = "", *, links: list[str] | None = None) -> Concept:
    return Concept(
        concept_id=concept_id,
        frontmatter=Frontmatter(type="Concept"),
        body=body,
        out_links=links or [],
    )


def _bundle(*concepts: Concept) -> Bundle:
    return Bundle(root_path="/tmp/b", concepts={c.concept_id: c for c in concepts})


def test_bundle_relative_link_is_absolute_and_standard() -> None:
    assert bundle_relative_link("policies/returns", "Returns") == "[Returns](/policies/returns.md)"


def test_is_bundle_relative() -> None:
    assert is_bundle_relative("/policies/returns.md")
    assert not is_bundle_relative("./returns.md")
    assert not is_bundle_relative("../returns.md")


def test_classify_link_marks_present_target() -> None:
    bundle = _bundle(_concept("a"), _concept("policies/returns"))
    resolved = classify_link("a", "/policies/returns.md", bundle)
    assert resolved == ResolvedLink(concept_id="policies/returns", present=True)
    assert not resolved.dangling


def test_classify_link_tolerates_dangling_target() -> None:
    # A bundle-relative link to a not-yet-written concept is valid, not malformed.
    bundle = _bundle(_concept("a"))
    resolved = classify_link("a", "/entities/not-written-yet.md", bundle)
    assert resolved is not None
    assert resolved.concept_id == "entities/not-written-yet"
    assert resolved.dangling


def test_classify_link_resolves_relative_targets() -> None:
    bundle = _bundle(_concept("policies/returns"), _concept("policies/refunds"))
    resolved = classify_link("policies/returns", "./refunds.md", bundle)
    assert resolved == ResolvedLink(concept_id="policies/refunds", present=True)


def test_classify_link_ignores_non_bundle_targets() -> None:
    bundle = _bundle(_concept("a"))
    assert classify_link("a", "https://example.com/x.md", bundle) is None
    assert classify_link("a", "#section", bundle) is None
    assert classify_link("a", "/assets/logo.png", bundle) is None
    # A path climbing above the bundle root is not an in-bundle link.
    assert classify_link("a", "../../outside.md", bundle) is None


def test_dangling_links_reports_only_absent_targets() -> None:
    bundle = _bundle(
        _concept("a", links=["b", "ghost"]),
        _concept("b", links=["a"]),
    )
    assert dangling_links(bundle) == {"a": ["ghost"]}
