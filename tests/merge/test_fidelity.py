"""Fidelity across sequential ingests — the M7 edit-drift acceptance test.

system_design §7.1 / §8.1 require fidelity preserved across >=20 sequential
ingests with no palimpsest decay. Because the body is a deterministic projection
of provenance-bearing claims (never a freehand LLM rewrite), 20 supersedes of one
claim leave an unrelated claim byte-identical, never drift the body from its
sources, and keep the written file OKF-conformant the whole way.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from kosha.extract import ConceptDraft
from kosha.merge import (
    LexicalClaimTargeter,
    assert_no_drift,
    create_concept,
    current_claims,
    is_reconstructable,
    merge_update,
    reconstruct_from_sources,
    write_concept,
)
from kosha.model import ClaimStatus, Source, SourceKind
from kosha.validate import validate_bundle

_START = datetime(2026, 1, 1, tzinfo=UTC)
_GOLD = "Gold members receive free return shipping."
_INGESTS = 20


def _source(source_id: str) -> Source:
    return Source(source_id=source_id, kind=SourceKind.MARKDOWN, location=f"file://{source_id}.md")


def _returns_statement(days: int) -> str:
    return f"Standard returns are accepted within {days} days of delivery."


def test_fidelity_20_ingests(tmp_path: Path) -> None:
    targeter = LexicalClaimTargeter()

    seed = ConceptDraft(
        title="Returns",
        body=f"{_returns_statement(30)}\n\n{_GOLD}",
        description="How returns are handled.",
        type="policy",
        source_id="s0",
    )
    concept = create_concept(seed, "policies/returns", _source("s0"), _START)
    sources: dict[str, str] = {"s0": f"{_returns_statement(30)}\n{_GOLD}"}
    # The unrelated claim we expect to survive every ingest untouched.
    gold_claim = next(c for c in concept.claims if c.statement == _GOLD)

    for i in range(1, _INGESTS + 1):
        statement = _returns_statement(30 + i)
        source_id = f"s{i}"
        draft = ConceptDraft(
            title="Returns",
            body=statement,
            description="How returns are handled.",
            type="policy",
            source_id=source_id,
        )
        concept = merge_update(
            concept, draft, _source(source_id), _START + timedelta(days=i), targeter=targeter
        )
        sources[source_id] = statement

        # 1. The body is exactly the claim projection — no freehand drift.
        assert_no_drift(concept)
        # 2. Every in-force claim traces back to a cited source.
        assert is_reconstructable(concept, sources)
        # 3. The unrelated claim is byte-identical and still current.
        survivor = next(
            c for c in current_claims(concept.claims) if c.claim_id == gold_claim.claim_id
        )
        assert survivor == gold_claim
        # 4. The written concept is OKF-conformant (`kosha validate` exit 0).
        write_concept(tmp_path, concept)
        assert validate_bundle(tmp_path).ok

    heads = current_claims(concept.claims)
    assert [c.statement for c in heads] == [_returns_statement(50), _GOLD]
    # Full lineage retained: 1 root returns claim + 20 supersessions + 1 gold = 22.
    assert len(concept.claims) == _INGESTS + 2
    superseded = [c for c in concept.claims if c.status is ClaimStatus.SUPERSEDED]
    assert len(superseded) == _INGESTS
    # The body reflects the latest source faithfully, with no trace of the telephone game.
    assert _returns_statement(50) in concept.body
    assert _returns_statement(30) not in concept.body
    assert _GOLD in concept.body
    # The concept remains reconstructable from its cited sources after 20 ingests.
    assert reconstruct_from_sources(concept, sources) == concept.body
    assert validate_bundle(tmp_path).ok


def test_fidelity_holds_when_two_claims_evolve_independently(tmp_path: Path) -> None:
    targeter = LexicalClaimTargeter()
    seed = ConceptDraft(
        title="Returns",
        body=f"{_returns_statement(30)}\n\n{_GOLD}",
        description="How returns are handled.",
        type="policy",
        source_id="s0",
    )
    concept = create_concept(seed, "policies/returns", _source("s0"), _START)
    sources: dict[str, str] = {"s0": f"{_returns_statement(30)}\n{_GOLD}"}

    # Alternate ingests: even revises the returns window, odd revises the gold perk.
    for i in range(1, 11):
        if i % 2 == 0:
            statement = _returns_statement(30 + i)
        else:
            statement = f"Gold members receive free return shipping on orders over {i} dollars."
        source_id = f"s{i}"
        draft = ConceptDraft(
            title="Returns",
            body=statement,
            description="How returns are handled.",
            type="policy",
            source_id=source_id,
        )
        concept = merge_update(
            concept, draft, _source(source_id), _START + timedelta(days=i), targeter=targeter
        )
        sources[source_id] = statement
        assert_no_drift(concept)
        assert is_reconstructable(concept, sources)

    # Exactly two in-force claims survive — one per evolving topic, never duplicated.
    assert len(current_claims(concept.claims)) == 2
    write_concept(tmp_path, concept)
    assert validate_bundle(tmp_path).ok
