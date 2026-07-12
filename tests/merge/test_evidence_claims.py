"""Claim minting, supersede, and contradiction reconcile carry evidence identity.

DEVELOPMENT_PLAN.md M3: every claim minted from an evidence-bound draft resolves
back to ``source_run_id`` / ``evidence_sha256`` -- through a straight CREATE, a
targeted supersede, and every branch of contradiction reconciliation (temporal,
authority, escalate). A draft with no evidence identity (e.g. one derived from a
secret-tainted document) mints claims with none, honestly.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from kosha.contradiction.detect import LexicalContradictionJudge
from kosha.contradiction.escalate import reconcile
from kosha.dedup.split import split_draft
from kosha.extract import ConceptDraft
from kosha.merge.claims import current_claims, make_claim, supersede_claim
from kosha.merge.create import claims_from_draft, create_concept
from kosha.model import Claim, Source, SourceKind
from kosha.pipeline.writer import apply_update
from kosha.providers import ExtractiveGenerationProvider

_T0 = datetime(2026, 1, 1, tzinfo=UTC)
_T1 = datetime(2026, 2, 1, tzinfo=UTC)
_JUDGE = LexicalContradictionJudge()
_DIGEST = "a" * 64
_DIGEST_2 = "b" * 64


def _source(source_id: str = "s1", *, authority: int = 0) -> Source:
    return Source(
        source_id=source_id, kind=SourceKind.MARKDOWN, location=source_id, authority_rank=authority
    )


def _draft(
    body: str,
    *,
    source_id: str = "s1",
    evidence_sha256: str | None = _DIGEST,
    source_run_id: str | None = "run-1",
) -> ConceptDraft:
    return ConceptDraft(
        title="Returns",
        body=body,
        description="Returns handling.",
        type="policy",
        source_id=source_id,
        evidence_sha256=evidence_sha256,
        source_run_id=source_run_id,
    )


# --- CREATE --------------------------------------------------------------------


def test_claims_from_draft_stamps_evidence_identity() -> None:
    draft = _draft("Returns within 30 days.\n\nGold members ship free.")
    claims = claims_from_draft(draft, _source(), _T0)
    assert all(c.evidence_sha256 == _DIGEST for c in claims)
    assert all(c.source_run_id == "run-1" for c in claims)


def test_create_concept_claims_carry_evidence_identity() -> None:
    draft = _draft("Returns within 30 days.")
    concept = create_concept(draft, "policies/returns", _source(), _T0)
    assert concept.claims[0].evidence_sha256 == _DIGEST
    assert concept.claims[0].source_run_id == "run-1"


def test_a_draft_with_no_evidence_identity_mints_claims_with_none() -> None:
    draft = _draft("Returns within 30 days.", evidence_sha256=None, source_run_id=None)
    claims = claims_from_draft(draft, _source(), _T0)
    assert claims[0].evidence_sha256 is None
    assert claims[0].source_run_id is None


# --- UPDATE: targeted supersede --------------------------------------------------


def test_supersede_claim_stamps_the_replacement_with_evidence_identity() -> None:
    old = make_claim("Returns within 30 days.", "s0", _T0)
    updated, replacement = supersede_claim(
        [old],
        old.claim_id,
        statement="Returns within 60 days.",
        source_id="s1",
        asserted_at=_T1,
        evidence_sha256=_DIGEST,
        source_run_id="run-1",
    )
    assert replacement.evidence_sha256 == _DIGEST
    assert replacement.source_run_id == "run-1"
    # The retired claim's own evidence identity is untouched.
    retired = next(c for c in updated if c.claim_id == old.claim_id)
    assert retired.evidence_sha256 is None


def test_apply_update_targeted_supersede_stamps_evidence_on_the_new_claim() -> None:
    base_draft = _draft(
        "Standard returns are accepted within 30 days of delivery.",
        source_id="s0",
        evidence_sha256=None,
        source_run_id=None,
    )
    existing = create_concept(base_draft, "policies/returns", _source("s0"), _T0)
    revising = _draft(
        "Standard returns are accepted within 30 days of delivery, with a receipt.",
        source_id="s1",
    )
    result = apply_update(
        existing,
        revising,
        _source("s1", authority=10),
        _T1,
        authority={"s0": 0, "s1": 10},
        targeter=_LexicalTargeter(),
        judge=_JUDGE,
    )
    heads = current_claims(result.concept.claims)
    assert heads[0].evidence_sha256 == _DIGEST
    assert heads[0].source_run_id == "run-1"


# --- UPDATE: contradiction reconcile ---------------------------------------------


def test_reconcile_temporal_supersede_stamps_the_winner_with_evidence() -> None:
    old = make_claim(
        "Standard returns are accepted within 30 days.", "s0", _T0, effective_from=_T0
    )
    new = make_claim(
        "Standard returns are accepted within 60 days.",
        "s1",
        _T1,
        effective_from=_T1,
        evidence_sha256=_DIGEST_2,
        source_run_id="run-2",
    )
    result = reconcile([old], new, authority={"s0": 1, "s1": 1}, judge=_JUDGE, asof=_T1)
    winner = next(c for c in result.claims if c.claim_id == new.claim_id)
    assert winner.evidence_sha256 == _DIGEST_2
    assert winner.source_run_id == "run-2"


def test_reconcile_authority_win_stamps_the_winner_with_evidence() -> None:
    old = make_claim("Standard returns are accepted within 30 days.", "s0", _T0)
    new = make_claim(
        "Standard returns are accepted within 60 days.",
        "s1",
        _T0,
        evidence_sha256=_DIGEST_2,
        source_run_id="run-2",
    )
    result = reconcile([old], new, authority={"s0": 0, "s1": 10}, judge=_JUDGE, asof=_T0)
    winner = next(c for c in result.claims if c.claim_id == new.claim_id)
    assert winner.evidence_sha256 == _DIGEST_2
    old_retained = next(c for c in result.claims if c.claim_id == old.claim_id)
    assert old_retained.evidence_sha256 is None  # untouched by reconciliation


def test_reconcile_escalation_retains_both_claims_evidence_identity() -> None:
    old = make_claim(
        "Standard returns are accepted within 30 days.",
        "s0",
        _T0,
        evidence_sha256="c" * 64,
        source_run_id="run-0",
    )
    new = make_claim(
        "Standard returns are accepted within 90 days.",
        "s1",
        _T0,
        evidence_sha256=_DIGEST_2,
        source_run_id="run-2",
    )
    result = reconcile([old], new, authority={"s0": 5, "s1": 5}, judge=_JUDGE, asof=_T0)
    assert result.escalated is True
    loser = next(c for c in result.claims if c.claim_id == new.claim_id)
    assert loser.evidence_sha256 == _DIGEST_2
    incumbent = next(c for c in result.claims if c.claim_id == old.claim_id)
    assert incumbent.evidence_sha256 == "c" * 64


# --- SPLIT: sub-drafts inherit the parent's evidence identity, not a re-derived one


def test_split_draft_propagates_the_parents_evidence_identity() -> None:
    draft = _draft("# Returns\n\nWithin 30 days.\n\n# Shipping\n\nFree for gold members.")
    sub_drafts = split_draft(draft, ExtractiveGenerationProvider())
    assert len(sub_drafts) >= 1
    assert all(sub.evidence_sha256 == _DIGEST for sub in sub_drafts)
    assert all(sub.source_run_id == "run-1" for sub in sub_drafts)


class _LexicalTargeter:
    """A supersede-everything targeter so the UPDATE test exercises supersede_claim."""

    def target(self, statement: str, candidates: Sequence[Claim]) -> str | None:
        return candidates[0].claim_id if candidates else None
