"""Parser behavior: concept_id derivation, frontmatter typing, body fidelity."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from kosha.okf import concept_id_from_path, parse_concept, parse_frontmatter
from kosha.okf.errors import FrontmatterError

ORDERS = """---
type: BigQuery Table
title: Orders
description: One row per completed customer order across all channels.
tags: [sales, orders, revenue]
timestamp: 2026-06-27T10:00:00Z
---

# Schema

Part of [customer lifetime value](/concepts/customer-lifetime-value.md).
"""


def test_concept_id_strips_md_suffix() -> None:
    assert concept_id_from_path("tables/orders.md") == "tables/orders"
    assert concept_id_from_path("root.md") == "root"


def test_concept_id_normalizes_backslashes() -> None:
    assert concept_id_from_path("tables\\orders.md") == "tables/orders"


def test_concept_id_rejects_non_md() -> None:
    with pytest.raises(ValueError, match="must end in"):
        concept_id_from_path("tables/orders.txt")


def test_parse_concept_types_frontmatter() -> None:
    concept = parse_concept("tables/orders.md", ORDERS)
    assert concept.concept_id == "tables/orders"
    assert concept.frontmatter.type == "BigQuery Table"
    assert concept.frontmatter.tags == ["sales", "orders", "revenue"]
    assert concept.frontmatter.timestamp == datetime(2026, 6, 27, 10, 0, tzinfo=UTC)


def test_parse_concept_keeps_body_verbatim() -> None:
    concept = parse_concept("tables/orders.md", ORDERS)
    assert concept.body.startswith("\n# Schema")
    assert "[customer lifetime value]" in concept.body


def test_parse_concept_preserves_unknown_keys() -> None:
    text = "---\ntype: Metric\nowner: data-team\n---\n\nbody\n"
    concept = parse_concept("metrics/clv.md", text)
    assert concept.frontmatter.model_extra == {"owner": "data-team"}


def test_parse_concept_derives_out_links() -> None:
    text = (
        "---\ntype: Playbook\n---\n\n"
        "See [orders](/tables/orders.md) and [neighbor](./peak.md) and "
        "[up](../entities/x.md#anchor) and [ext](https://example.com/y.md).\n"
    )
    concept = parse_concept("playbooks/diag.md", text)
    assert concept.out_links == ["tables/orders", "playbooks/peak", "entities/x"]


def test_out_links_skip_bundle_escaping_paths() -> None:
    text = "---\ntype: Concept\n---\n\nSee [up](../../outside.md) and [ok](/in/bounds.md).\n"
    concept = parse_concept("a/b.md", text)
    assert concept.out_links == ["in/bounds"]


def test_parse_frontmatter_missing_type_raises_typed_error() -> None:
    with pytest.raises(FrontmatterError, match="validation"):
        parse_frontmatter("---\ntitle: no type here\n---\nbody\n")


def test_parse_frontmatter_missing_block_raises() -> None:
    with pytest.raises(FrontmatterError):
        parse_frontmatter("# No frontmatter here\n")


def test_parse_frontmatter_invalid_yaml_raises() -> None:
    with pytest.raises(FrontmatterError):
        parse_frontmatter("---\ntype: : bad\n: nope\n---\nbody\n")


def test_parse_frontmatter_non_mapping_raises() -> None:
    with pytest.raises(FrontmatterError):
        parse_frontmatter("---\n- just\n- a\n- list\n---\nbody\n")
