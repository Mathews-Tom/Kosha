"""Apply a dedup decision to a concept through the M7 + M9 claim layer.

This is where the merge/writer (M7) and the contradiction lane (M9) compose into
the pipeline's writer (system_design §4.1):

* **CREATE** mints a new concept from the draft (M7 ``create_concept``).
* **UPDATE** merges each incoming statement into the matched concept. A statement
  that revises a specific in-force claim *without* materially conflicting is a
  targeted supersede (M7); an additive or conflicting statement goes through the
  M9 ``reconcile`` lane — temporal → source-authority → escalate — so a conflict
  is resolved deterministically or surfaced for the human, and **no prior claim is
  ever dropped or rewritten in place** (``assert_no_silent_overwrite``).

A concept loaded from disk carries only a body (the on-disk artifact has no claim
provenance), so :func:`hydrate_claims` seeds its claim set from the body before the
first merge — the claim layer the supersede/reconcile machinery needs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from kosha.contradiction.detect import ContradictionJudge, detect_conflict
from kosha.contradiction.escalate import Escalation, assert_no_silent_overwrite, reconcile
from kosha.extract import ConceptDraft
from kosha.indexlog.index import directory_of
from kosha.link.edits import strip_managed_sections
from kosha.merge.claims import current_claims, make_claim, render_body, supersede_claim
from kosha.merge.create import segment_statements, source_citation
from kosha.merge.update import ClaimTargeter
from kosha.model import Claim, Concept, Source
from kosha.okf.parse import concept_id_from_path
from kosha.plan import ContradictionState

_SLUG = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class UpdateResult:
    """The outcome of merging a draft into an existing concept."""

    concept: Concept
    escalations: tuple[Escalation, ...]
    contradiction: ContradictionState
    superseded: bool


def hydrate_claims(concept: Concept, *, asserted_at: datetime) -> Concept:
    """Seed a disk-loaded concept's claim set from its body (idempotent).

    A concept that already carries claims is returned unchanged. Otherwise its
    body — minus the managed link sections — is segmented into one claim per
    paragraph, stamped with an incumbent ``bundle:<id>`` provenance (authority 0)
    so a later, higher-authority source can supersede it.
    """
    if concept.claims:
        return concept
    statements = segment_statements(strip_managed_sections(concept.body))
    if not statements:
        front = concept.frontmatter
        statements = [front.description or front.title or concept.concept_id]
    source_id = f"bundle:{concept.concept_id}"
    when = concept.frontmatter.timestamp or asserted_at
    claims = [
        make_claim(statement, source_id, when, effective_from=concept.frontmatter.effective_from)
        for statement in statements
    ]
    return concept.model_copy(update={"claims": claims, "body": render_body(claims)})


def apply_update(
    existing: Concept,
    draft: ConceptDraft,
    source: Source,
    asserted_at: datetime,
    *,
    authority: dict[str, int],
    targeter: ClaimTargeter,
    judge: ContradictionJudge,
) -> UpdateResult:
    """Merge ``draft`` into ``existing`` through the M7 + M9 claim layer."""
    concept = hydrate_claims(existing, asserted_at=asserted_at)
    before = list(concept.claims)
    claims = list(concept.claims)
    citation = source_citation(source)
    escalations: list[Escalation] = []
    state = ContradictionState.NONE
    superseded = False

    for statement in segment_statements(draft.body) or [draft.description]:
        in_force = current_claims(claims)
        if any(claim.statement == statement for claim in in_force):
            continue  # verbatim re-assert: no churn
        target_id = targeter.target(statement, in_force)
        targets_conflict = target_id is not None and detect_conflict(
            _by_id(claims, target_id), statement, judge=judge
        ).conflicting
        if target_id is not None and not targets_conflict:
            # Non-conflicting revision of a specific claim: M7 targeted supersede.
            claims, _ = supersede_claim(
                claims,
                target_id,
                statement=statement,
                source_id=source.source_id,
                asserted_at=asserted_at,
                citations=[citation],
            )
            superseded = True
            continue
        # Additive or conflicting: M9 reconcile (temporal -> authority -> escalate).
        new_claim = make_claim(statement, source.source_id, asserted_at, citations=[citation])
        reconciliation = reconcile(
            claims, new_claim, authority=authority, judge=judge, asof=asserted_at
        )
        assert_no_silent_overwrite(claims, reconciliation.claims)
        claims = list(reconciliation.claims)
        if reconciliation.conflicting:
            if reconciliation.escalated:
                state = ContradictionState.ESCALATED
                if reconciliation.escalation is not None:
                    escalations.append(reconciliation.escalation)
            else:
                superseded = True
                if state is not ContradictionState.ESCALATED:
                    state = ContradictionState.RESOLVED

    assert_no_silent_overwrite(before, claims)
    frontmatter = concept.frontmatter.model_copy(update={"timestamp": asserted_at})
    updated = concept.model_copy(
        update={"claims": claims, "body": render_body(claims), "frontmatter": frontmatter}
    )
    return UpdateResult(updated, tuple(escalations), state, superseded)


def new_concept_id(draft: ConceptDraft, source: Source, *, taken: set[str]) -> str:
    """Derive the path a CREATE draft becomes, from its source path and title.

    The new concept inherits the source file's directory (so a source folder that
    mirrors the bundle layout places concepts where they belong) and a slug of the
    draft title. Colliding with an existing concept is a bug, not a CREATE — it is
    raised rather than silently overwriting.
    """
    base_dir = directory_of(concept_id_from_path(source.source_id))
    slug = _SLUG.sub("-", draft.title.lower()).strip("-") or "concept"
    concept_id = f"{base_dir}/{slug}" if base_dir else slug
    if concept_id in taken:
        raise ValueError(f"CREATE target {concept_id!r} already exists; expected an UPDATE")
    return concept_id


def _by_id(claims: list[Claim], claim_id: str) -> Claim:
    for claim in claims:
        if claim.claim_id == claim_id:
            return claim
    raise KeyError(f"no claim {claim_id!r} in concept")
