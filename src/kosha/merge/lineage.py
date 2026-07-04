"""Claim lineage: reconstruct supersede and contradiction history (M7 PR-1).

The claim layer (:mod:`kosha.merge.claims`) already carries everything a
lineage answer needs — ``supersedes`` chains a replacement back to the claim it
retired, and ``contradicts`` (M7) chains a losing claim back to the incumbent it
was rejected against. This module is the pure read side over that structure: it
never mutates a claim, only reconstructs the ordered views a consumer asks for —
"what is this concept's whole claim history", "what is the full chain a given
claim belongs to", and "what was rejected against a given claim" — so the MCP
lineage tool (PR-2) and the compliance export (PR-3) share one deterministic
implementation instead of each re-walking the claim list.

Deterministic ordering (by ``asserted_at`` then ``claim_id``) matters here for
the same reason it matters to :mod:`kosha.plan.assemble`: two runs over the same
claim set must produce byte-identical output for the "exports are deterministic"
acceptance criterion.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from kosha.model import Claim, ClaimStatus


@dataclass(frozen=True)
class ClaimLineageEntry:
    """One claim's full provenance, as surfaced to a lineage consumer."""

    claim_id: str
    statement: str
    status: ClaimStatus
    source_id: str
    asserted_at: datetime
    reviewer: str | None
    supersedes: str | None
    contradicts: str | None
    citations: tuple[str, ...]
    effective_from: datetime | None
    effective_to: datetime | None


def _entry(claim: Claim) -> ClaimLineageEntry:
    return ClaimLineageEntry(
        claim_id=claim.claim_id,
        statement=claim.statement,
        status=claim.status,
        source_id=claim.source_id,
        asserted_at=claim.asserted_at,
        reviewer=claim.reviewer,
        supersedes=claim.supersedes,
        contradicts=claim.contradicts,
        citations=tuple(claim.citations),
        effective_from=claim.effective_from,
        effective_to=claim.effective_to,
    )


def _sort_key(claim: Claim) -> tuple[datetime, str]:
    return (claim.asserted_at, claim.claim_id)


def concept_history(claims: Sequence[Claim]) -> list[ClaimLineageEntry]:
    """Return every claim ever tracked in ``claims``, oldest first.

    This is the full audit trail for a concept: current, superseded, and
    contradicted claims alike, in one deterministic, chronological listing —
    the view a consumer browses before drilling into a specific claim's chain
    with :func:`claim_chain`.
    """
    return [_entry(claim) for claim in sorted(claims, key=_sort_key)]


def claim_chain(claims: Sequence[Claim], claim_id: str) -> list[ClaimLineageEntry]:
    """Return the supersede chain ``claim_id`` belongs to, oldest to newest.

    A chain is a root claim (``supersedes is None``) plus the line of
    replacements that retired it, one per ``supersedes`` link — the same chain
    :func:`kosha.merge.claims.current_claims` walks to find each chain's live
    head. Passing any member's ``claim_id`` returns the whole chain: the
    predecessors it superseded and the replacement that later superseded it, so
    "what superseded this claim, when, from which source, under which approver
    identity" is answered by reading forward from the requested claim.

    Raises :class:`KeyError` when ``claim_id`` is not in ``claims``.
    """
    by_id = {claim.claim_id: claim for claim in claims}
    if claim_id not in by_id:
        raise KeyError(f"no claim {claim_id!r} in concept")
    by_supersedes = {c.supersedes: c for c in claims if c.supersedes is not None}

    root = by_id[claim_id]
    while root.supersedes is not None and root.supersedes in by_id:
        root = by_id[root.supersedes]

    chain = [root]
    while chain[-1].claim_id in by_supersedes:
        chain.append(by_supersedes[chain[-1].claim_id])
    return [_entry(claim) for claim in chain]


def contested_by(claims: Sequence[Claim], claim_id: str) -> list[ClaimLineageEntry]:
    """Return the claims rejected specifically against ``claim_id``.

    These are losing claims the resolution policy held as ``contradicted``
    without a ``supersedes`` link — a competing assertion that lost (by
    authority or escalation) rather than a chain replacement. Ordered by
    assertion time.
    """
    losers = [claim for claim in claims if claim.contradicts == claim_id]
    return [_entry(claim) for claim in sorted(losers, key=_sort_key)]
