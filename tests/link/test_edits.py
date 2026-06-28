"""Link insertion and backlink computation (M8 PR-2)."""

from __future__ import annotations

from pathlib import Path

from kosha.link import (
    LexicalRelator,
    Relation,
    apply_links,
    changed_concept_ids,
    compute_backlinks,
    crosslink,
    write_concepts,
)
from kosha.model import Bundle, Concept, Frontmatter
from kosha.okf import load_bundle
from kosha.validate import validate_bundle


def _concept(
    concept_id: str,
    *,
    title: str,
    description: str = "",
    body: str,
    tags: list[str] | None = None,
    links: list[str] | None = None,
) -> Concept:
    return Concept(
        concept_id=concept_id,
        frontmatter=Frontmatter(
            type="Concept", title=title, description=description, tags=tags or []
        ),
        body=body,
        out_links=links or [],
    )


_RETURNS = _concept(
    "policies/returns",
    title="Returns",
    description="Customers may return unworn items within the return window.",
    body="\n# Returns\n\nA return is accepted when the item is unworn and inside the window.\n",
    tags=["returns"],
)
_REFUNDS = _concept(
    "policies/refunds",
    title="Refunds",
    description="A refund is issued to the original payment card after a return is approved.",
    body="\n# Refunds\n\nRefunds for an approved return post to the original payment card.\n",
    tags=["returns"],
)


def _bundle(*concepts: Concept) -> Bundle:
    return Bundle(root_path="/tmp/b", concepts={c.concept_id: c for c in concepts})


def test_apply_links_inserts_bundle_relative_related_section() -> None:
    bundle = _bundle(_RETURNS, _REFUNDS)
    linked = apply_links(bundle, [Relation(source="policies/returns", target="policies/refunds")])
    body = linked.concepts["policies/returns"].body
    assert "# Related" in body
    assert "* [Refunds](/policies/refunds.md)" in body
    assert "[[" not in body  # never a wikilink


def test_apply_links_records_forward_out_links_excluding_backlinks() -> None:
    bundle = _bundle(_RETURNS, _REFUNDS)
    linked = apply_links(bundle, [Relation(source="policies/returns", target="policies/refunds")])
    # The Related link is a forward edge; the Backlinks section is not.
    assert linked.concepts["policies/returns"].out_links == ["policies/refunds"]


def test_compute_backlinks_is_reverse_of_forward_edges() -> None:
    bundle = _bundle(_RETURNS, _REFUNDS)
    linked = crosslink(bundle, LexicalRelator())
    backlinks = compute_backlinks(linked)
    assert backlinks["policies/refunds"] == ["policies/returns"]
    assert backlinks["policies/returns"] == ["policies/refunds"]


def test_crosslink_materializes_backlinks_section() -> None:
    linked = crosslink(_bundle(_RETURNS, _REFUNDS), LexicalRelator())
    body = linked.concepts["policies/refunds"].body
    assert "# Backlinks" in body
    assert "* [Returns](/policies/returns.md)" in body


def test_crosslink_is_idempotent() -> None:
    once = crosslink(_bundle(_RETURNS, _REFUNDS), LexicalRelator())
    twice = crosslink(once, LexicalRelator())
    assert {k: v.body for k, v in once.concepts.items()} == {
        k: v.body for k, v in twice.concepts.items()
    }


def test_apply_links_does_not_duplicate_a_prose_link() -> None:
    # The author already linked returns -> refunds in prose; discovery skips it.
    returns = _concept(
        "policies/returns",
        title="Returns",
        description=_RETURNS.frontmatter.description or "",
        body="\n# Returns\n\nSee [refunds](/policies/refunds.md) for the money path.\n",
        tags=["returns"],
        links=["policies/refunds"],
    )
    linked = crosslink(_bundle(returns, _REFUNDS), LexicalRelator())
    returns_body = linked.concepts["policies/returns"].body
    # The only candidate is already a prose link, so no # Related section is added.
    assert "# Related" not in returns_body
    assert "[refunds](/policies/refunds.md)" in returns_body


def test_apply_links_tolerates_a_dangling_target() -> None:
    bundle = _bundle(_RETURNS)
    linked = apply_links(
        bundle, [Relation(source="policies/returns", target="policies/exchanges")]
    )
    body = linked.concepts["policies/returns"].body
    # The target concept is not in the bundle; the link is still emitted (dangling).
    assert "* [policies/exchanges](/policies/exchanges.md)" in body


def test_changed_concept_ids_tracks_body_edits() -> None:
    bundle = _bundle(_RETURNS, _REFUNDS)
    linked = crosslink(bundle, LexicalRelator())
    assert changed_concept_ids(bundle, linked) == ["policies/refunds", "policies/returns"]


def test_written_crosslinked_bundle_is_conformant(tmp_path: Path) -> None:
    bundle = _bundle(_RETURNS, _REFUNDS)
    linked = crosslink(bundle, LexicalRelator())
    write_concepts(tmp_path, linked, linked.concepts)

    report = validate_bundle(tmp_path)
    assert report.ok
    assert report.errors == []

    # The links round-trip: reloaded forward edges resolve to bundle concepts.
    reloaded = load_bundle(tmp_path)
    assert "policies/refunds" in reloaded.concepts["policies/returns"].out_links
