"""Claim lifecycle and body projection — the edit-drift guard's core.

A concept body is never rewritten freehand. It is a *deterministic projection*
of the concept's current claims (system_design §3 "On the CLAIM entity", §4.1).
A merge therefore supersedes a specific claim — marks the retired claim
``superseded`` and appends a replacement linked back by ``supersedes`` — instead
of editing prose, which is what keeps fidelity stable across many ingests (the
"telephone game" the §7.1 edit-drift failure mode warns about).

``render_body`` is the single projection function shared by create, update, and
the reconstruct check: same claims in, byte-identical body out. Because a
superseded claim's replacement takes its predecessor's slot in render order, an
UPDATE to one claim leaves every unrelated claim's rendered text untouched.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import datetime

from kosha.model import Claim, ClaimStatus
from kosha.okf.serialize import render_citations


def mint_claim_id(statement: str, source_id: str, asserted_at: datetime) -> str:
    """Return a stable, content-addressed id for a claim.

    The id is derived from the statement, its source, and when it was asserted,
    so re-deriving the same claim yields the same id (deterministic audit) while
    a re-asserted or edited statement gets a fresh one. BLAKE2b is used for the
    same cross-machine stability reason as the lexical embedding provider.
    """
    payload = f"{source_id}|{asserted_at.isoformat()}|{statement}".encode()
    return hashlib.blake2b(payload, digest_size=8).hexdigest()


def make_claim(
    statement: str,
    source_id: str,
    asserted_at: datetime,
    *,
    citations: Sequence[str] = (),
    supersedes: str | None = None,
    effective_from: datetime | None = None,
    effective_to: datetime | None = None,
    reviewer: str | None = None,
    source_run_id: str | None = None,
    evidence_sha256: str | None = None,
) -> Claim:
    """Build a ``current`` claim with a content-addressed id."""
    return Claim(
        claim_id=mint_claim_id(statement, source_id, asserted_at),
        statement=statement,
        source_id=source_id,
        asserted_at=asserted_at,
        status=ClaimStatus.CURRENT,
        citations=list(citations),
        supersedes=supersedes,
        effective_from=effective_from,
        effective_to=effective_to,
        reviewer=reviewer,
        source_run_id=source_run_id,
        evidence_sha256=evidence_sha256,
    )


def supersede_claim(
    claims: Sequence[Claim],
    target_id: str,
    *,
    statement: str,
    source_id: str,
    asserted_at: datetime,
    citations: Sequence[str] = (),
    reviewer: str | None = None,
    source_run_id: str | None = None,
    evidence_sha256: str | None = None,
) -> tuple[list[Claim], Claim]:
    """Retire ``target_id`` and append a replacement claim.

    Returns the new claim list (the target marked ``superseded``, the
    replacement appended) and the replacement claim. The target must be a claim
    that is currently in force; superseding an already-retired claim is a caller
    bug and raises.
    """
    target = _find(claims, target_id)
    if target.status is not ClaimStatus.CURRENT:
        raise ValueError(f"cannot supersede non-current claim {target_id!r} ({target.status})")
    replacement = make_claim(
        statement,
        source_id,
        asserted_at,
        citations=citations,
        supersedes=target_id,
        reviewer=reviewer,
        source_run_id=source_run_id,
        evidence_sha256=evidence_sha256,
    )
    updated = [
        claim.model_copy(update={"status": ClaimStatus.SUPERSEDED})
        if claim.claim_id == target_id
        else claim
        for claim in claims
    ]
    updated.append(replacement)
    return updated, replacement


def current_claims(claims: Sequence[Claim]) -> list[Claim]:
    """Return the in-force claims, each chain's head, in original chain order.

    A chain is a root claim (``supersedes is None``) plus the line of
    replacements that retired it. The head (newest, un-superseded) renders in the
    root's position, so superseding a claim never reorders the unrelated ones.
    """
    by_supersedes = {c.supersedes: c for c in claims if c.supersedes is not None}
    heads: list[Claim] = []
    for root in (c for c in claims if c.supersedes is None):
        head = root
        while head.claim_id in by_supersedes:
            head = by_supersedes[head.claim_id]
        if head.status is ClaimStatus.CURRENT:
            heads.append(head)
    return heads


def render_body(claims: Sequence[Claim]) -> str:
    """Project the current claims to an OKF concept body.

    Each current claim's statement renders as a paragraph in chain order, then a
    single ``# Citations`` section aggregates their citations (first-seen order,
    de-duplicated). This is a pure function of the claims: the only source of the
    body, so a body that differs from it has drifted (see ``reconstruct``).
    """
    return render_claim_set(current_claims(claims))


def render_claim_set(claims: Sequence[Claim]) -> str:
    """Project an already-selected claim set to an OKF body, in the given order.

    The pure projection both :func:`render_body` and the consumer surface's
    temporal filter share. :func:`render_body` pre-selects the current chain heads;
    ``load_concept`` pre-selects the in-force claims (via
    :func:`kosha.contradiction.effective_claims`) so an expired claim never renders.
    Each statement becomes a paragraph in the supplied order, followed by one
    de-duplicated ``# Citations`` section.
    """
    body = "\n\n".join(claim.statement for claim in claims)
    citations: list[str] = []
    for claim in claims:
        for citation in claim.citations:
            if citation not in citations:
                citations.append(citation)
    rendered = render_citations(citations)
    if not rendered:
        return body
    return f"{body}\n\n{rendered}" if body else rendered


def _find(claims: Sequence[Claim], claim_id: str) -> Claim:
    for claim in claims:
        if claim.claim_id == claim_id:
            return claim
    raise KeyError(f"no claim {claim_id!r} in concept")
