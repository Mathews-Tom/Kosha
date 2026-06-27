"""Tests for the bundle loader against the golden Northwind corpus."""

from __future__ import annotations

from pathlib import Path

import pytest

from kosha.model import Bundle
from kosha.okf import load_bundle
from kosha.validate import validate_bundle

NORTHWIND = Path(__file__).resolve().parents[2] / "bundles" / "northwind"

# Every concept document the golden corpus is expected to expose (index/log excluded).
EXPECTED_CONCEPT_IDS = {
    "policies/returns/standard",
    "policies/returns/gold-members",
    "policies/shipping",
    "policies/refunds",
    "policies/exchanges",
    "playbooks/handle-return",
    "playbooks/escalate-complaint",
    "entities/membership-tier",
    "entities/customer",
    "entities/order",
    "references/glossary",
    "references/channels",
}


def test_load_bundle_collects_every_concept_and_skips_reserved_files() -> None:
    bundle = load_bundle(NORTHWIND)
    assert isinstance(bundle, Bundle)
    assert set(bundle.concepts) == EXPECTED_CONCEPT_IDS
    # Reserved structure files never become concepts.
    assert not any(cid.endswith("index") or cid.endswith("log") for cid in bundle.concepts)


def test_loaded_concept_keeps_typed_frontmatter_and_out_links() -> None:
    bundle = load_bundle(NORTHWIND)
    standard = bundle.concepts["policies/returns/standard"]
    assert standard.frontmatter.type == "Policy"
    assert standard.frontmatter.title == "Standard Return Window"
    # The standard window links onward to the tier and the gold exception.
    assert "entities/membership-tier" in standard.out_links
    assert "policies/returns/gold-members" in standard.out_links


def test_golden_corpus_is_okf_conformant() -> None:
    report = validate_bundle(NORTHWIND)
    assert report.ok
    assert report.errors == []
    # A golden corpus is fully linked: no broken-link or granularity warnings.
    assert report.warnings == []


def test_load_bundle_rejects_a_non_directory(tmp_path: Path) -> None:
    not_a_dir = tmp_path / "nope.md"
    not_a_dir.write_text("x", encoding="utf-8")
    with pytest.raises(NotADirectoryError):
        load_bundle(not_a_dir)
