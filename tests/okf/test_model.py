"""Invariants of the OKF typed boundary that later milestones rely on."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from kosha.model import (
    Claim,
    ClaimStatus,
    Concept,
    Frontmatter,
)


def test_frontmatter_requires_type() -> None:
    with pytest.raises(ValidationError):
        Frontmatter()  # type: ignore[call-arg]


def test_frontmatter_preserves_unknown_keys() -> None:
    fm = Frontmatter(type="BigQuery Table", owner="data-team", priority=3)
    assert fm.model_extra == {"owner": "data-team", "priority": 3}
    assert fm.model_dump()["owner"] == "data-team"


def test_frontmatter_tags_default_is_independent() -> None:
    a = Frontmatter(type="Metric")
    b = Frontmatter(type="Metric")
    a.tags.append("x")
    assert b.tags == []


def test_claim_defaults_to_current() -> None:
    claim = Claim(
        claim_id="c1",
        statement="Returns are accepted within 30 days.",
        source_id="src1",
        asserted_at=datetime(2026, 6, 27, tzinfo=UTC),
    )
    assert claim.status is ClaimStatus.CURRENT


def test_claim_status_values() -> None:
    assert {s.value for s in ClaimStatus} == {"current", "superseded", "contradicted"}


def test_concept_composes_frontmatter_and_claims() -> None:
    concept = Concept(
        concept_id="tables/orders",
        frontmatter=Frontmatter(type="BigQuery Table"),
        body="# Schema\n",
        claims=[
            Claim(
                claim_id="c1",
                statement="One row per order.",
                source_id="src1",
                asserted_at=datetime(2026, 6, 27, tzinfo=UTC),
            )
        ],
        out_links=["tables/customers"],
    )
    assert concept.concept_id == "tables/orders"
    assert concept.claims[0].status is ClaimStatus.CURRENT
    assert concept.out_links == ["tables/customers"]
