"""Serializer output shape and writer conformance guards."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from kosha.model import Concept, Frontmatter, IndexDoc, IndexEntry, IndexSection
from kosha.okf import (
    render_citations,
    serialize_concept,
    serialize_frontmatter,
    serialize_index,
)
from kosha.okf.errors import WikilinkError


def test_frontmatter_canonical_order_and_styles() -> None:
    fm = Frontmatter(
        type="BigQuery Table",
        title="Orders",
        tags=["sales", "orders"],
        timestamp=datetime(2026, 6, 27, 10, 0, tzinfo=UTC),
        owner="data-team",
    )
    assert serialize_frontmatter(fm) == (
        "type: BigQuery Table\n"
        "title: Orders\n"
        "tags: [sales, orders]\n"
        "timestamp: 2026-06-27T10:00:00Z\n"
        "owner: data-team\n"
    )


def test_frontmatter_drops_none_and_empty_lists() -> None:
    out = serialize_frontmatter(Frontmatter(type="Metric"))
    assert out == "type: Metric\n"
    assert "tags:" not in out
    assert "title:" not in out


def test_frontmatter_does_not_wrap_long_scalars() -> None:
    long_desc = "A long description that comfortably exceeds the eighty column PyYAML fold width"
    out = serialize_frontmatter(Frontmatter(type="Metric", description=long_desc))
    assert out == f"type: Metric\ndescription: {long_desc}\n"


def test_frontmatter_preserves_subsecond_precision() -> None:
    fm = Frontmatter(type="Metric", timestamp=datetime(2026, 6, 27, 10, 0, 0, 500000, tzinfo=UTC))
    assert serialize_frontmatter(fm) == "type: Metric\ntimestamp: 2026-06-27T10:00:00.500000Z\n"


def test_serialize_concept_wraps_body() -> None:
    concept = Concept(
        concept_id="metrics/clv",
        frontmatter=Frontmatter(type="Metric", title="CLV"),
        body="\n# Definition\n\nAverage value.\n",
    )
    assert serialize_concept(concept) == (
        "---\ntype: Metric\ntitle: CLV\n---\n\n# Definition\n\nAverage value.\n"
    )


def test_serialize_concept_rejects_wikilinks() -> None:
    concept = Concept(
        concept_id="x",
        frontmatter=Frontmatter(type="Concept"),
        body="See [[orders]] for details.\n",
    )
    with pytest.raises(WikilinkError, match="wikilink"):
        serialize_concept(concept)


def test_serialize_concept_allows_brackets_in_code() -> None:
    inline = Concept(
        concept_id="m",
        frontmatter=Frontmatter(type="Metric"),
        body="Use `df[[\"col\"]]` to select a column.\n",
    )
    fenced = Concept(
        concept_id="m",
        frontmatter=Frontmatter(type="Metric"),
        body="```python\nx[[1]]\n```\n",
    )
    assert serialize_concept(inline).endswith('select a column.\n')
    assert serialize_concept(fenced).endswith("```\n")


def _sample_index(*, root: bool) -> IndexDoc:
    return IndexDoc(
        okf_version="0.1" if root else None,
        sections=[
            IndexSection(
                heading="Tables",
                entries=[
                    IndexEntry(
                        title="Orders",
                        target="tables/orders",
                        description="One row per order.",
                    ),
                    IndexEntry(title="Customers", target="tables/customers"),
                ],
            )
        ],
    )


def test_index_never_emits_type() -> None:
    assert "type:" not in serialize_index(_sample_index(root=True))
    assert "type:" not in serialize_index(_sample_index(root=False))


def test_index_links_are_bundle_relative() -> None:
    out = serialize_index(_sample_index(root=False))
    assert "[Orders](/tables/orders.md)" in out
    assert "[Customers](/tables/customers.md)" in out
    assert "](tables/" not in out  # never relative


def test_index_root_carries_only_okf_version() -> None:
    out = serialize_index(_sample_index(root=True))
    assert out.startswith("---\nokf_version: '0.1'\n---\n")


def test_index_non_root_has_no_frontmatter() -> None:
    assert not serialize_index(_sample_index(root=False)).startswith("---")


def test_render_citations_numbers_entries() -> None:
    out = render_citations(["[A](https://a)", "[B](https://b)"])
    assert out == "# Citations\n[1] [A](https://a)\n[2] [B](https://b)\n"


def test_render_citations_empty_is_blank() -> None:
    assert render_citations([]) == ""
