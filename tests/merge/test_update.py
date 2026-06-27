"""UPDATE path: claim-targeted body merge (M7 PR-3)."""

from __future__ import annotations

from datetime import UTC, datetime

from kosha.extract import ConceptDraft
from kosha.merge import (
    GenerationClaimTargeter,
    LexicalClaimTargeter,
    build_targeting_prompt,
    create_concept,
    current_claims,
    merge_update,
    parse_target,
)
from kosha.model import ClaimStatus, Source, SourceKind
from kosha.providers.base import Generation, Usage

_T0 = datetime(2026, 1, 1, tzinfo=UTC)
_T1 = datetime(2026, 2, 1, tzinfo=UTC)

_RETURNS = "Standard returns are accepted within 30 days of delivery."
_GOLD = "Gold members receive free return shipping."


def _source(source_id: str, title: str | None = None) -> Source:
    return Source(
        source_id=source_id,
        kind=SourceKind.MARKDOWN,
        location=f"file://{source_id}.md",
        title=title,
    )


def _base():
    draft = ConceptDraft(
        title="Returns",
        body=f"{_RETURNS}\n\n{_GOLD}",
        description="Returns handling.",
        type="policy",
        source_id="s1",
    )
    return create_concept(draft, "policies/returns", _source("s1"), _T0)


def _update_draft(body: str, source_id: str = "s2") -> ConceptDraft:
    return ConceptDraft(
        title="Returns",
        body=body,
        description="Returns handling.",
        type="policy",
        source_id=source_id,
    )


class _FixedProvider:
    """A generation provider returning a preset response, for targeter tests."""

    def __init__(self, text: str) -> None:
        self._text = text

    @property
    def name(self) -> str:
        return "fixed"

    def generate(self, query: str, context: str) -> Generation:
        return Generation(text=self._text, usage=Usage(prompt_tokens=0, completion_tokens=0))


def test_lexical_targeter_picks_the_revised_claim() -> None:
    concept = _base()
    targeter = LexicalClaimTargeter()
    new = "Standard returns are accepted within 60 days of delivery."
    target_id = targeter.target(new, current_claims(concept.claims))
    assert target_id == concept.claims[0].claim_id


def test_lexical_targeter_returns_none_for_a_novel_statement() -> None:
    concept = _base()
    targeter = LexicalClaimTargeter()
    candidates = current_claims(concept.claims)
    assert targeter.target("Refunds post to the original card.", candidates) is None


def test_merge_update_supersedes_only_the_targeted_claim() -> None:
    concept = _base()
    gold = concept.claims[1]
    new = "Standard returns are accepted within 60 days of delivery."
    updated = merge_update(
        concept, _update_draft(new), _source("s2"), _T1, targeter=LexicalClaimTargeter()
    )

    heads = current_claims(updated.claims)
    statements = [c.statement for c in heads]
    assert new in statements
    assert _RETURNS not in statements
    # The unrelated claim survives byte-identical and stays current.
    survivor = next(c for c in heads if c.claim_id == gold.claim_id)
    assert survivor == gold
    # Body is the projection: new text present, old gone, unrelated intact.
    assert new in updated.body
    assert _RETURNS not in updated.body
    assert _GOLD in updated.body
    # The retired claim is kept as history, marked superseded.
    retired = next(c for c in updated.claims if c.claim_id == concept.claims[0].claim_id)
    assert retired.status is ClaimStatus.SUPERSEDED
    assert updated.frontmatter.timestamp == _T1


def test_merge_update_appends_a_novel_claim() -> None:
    concept = _base()
    new = "Refunds post to the original card after approval."
    updated = merge_update(
        concept, _update_draft(new), _source("s2"), _T1, targeter=LexicalClaimTargeter()
    )
    statements = [c.statement for c in current_claims(updated.claims)]
    assert statements == [_RETURNS, _GOLD, new]
    assert len(updated.claims) == 3


def test_merge_update_is_idempotent_on_verbatim_reingest() -> None:
    concept = _base()
    # Re-ingesting the exact same body targets each claim but changes nothing.
    same = merge_update(
        concept, _update_draft(f"{_RETURNS}\n\n{_GOLD}"), _source("s2"), _T1,
        targeter=LexicalClaimTargeter(),
    )
    assert same is concept


def test_parse_target_reads_numbers_and_none() -> None:
    concept = _base()
    candidates = current_claims(concept.claims)
    assert parse_target("1", candidates) == candidates[0].claim_id
    assert parse_target("Claim 2.", candidates) == candidates[1].claim_id
    assert parse_target("NONE", candidates) is None
    assert parse_target("99", candidates) is None


def test_build_targeting_prompt_lists_candidates() -> None:
    concept = _base()
    _, context = build_targeting_prompt("x", current_claims(concept.claims))
    assert "1. " + _RETURNS in context
    assert "2. " + _GOLD in context


def test_generation_targeter_resolves_via_provider() -> None:
    concept = _base()
    targeter = GenerationClaimTargeter(_FixedProvider("1"))
    new = "Standard returns are accepted within 60 days of delivery."
    assert targeter.target(new, current_claims(concept.claims)) == concept.claims[0].claim_id
    none_targeter = GenerationClaimTargeter(_FixedProvider("NONE"))
    assert none_targeter.target(new, current_claims(concept.claims)) is None
