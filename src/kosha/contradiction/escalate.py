"""Reconcile a new claim against prior claims; escalate the residue (§4.3.1).

This is where detection, policy, and the never-silent-overwrite invariant meet.
:func:`reconcile` takes a concept's claims and one incoming claim, detects a
material conflict against the in-force claims, resolves it by the deterministic
policy, and applies the result to the claim list:

* **temporal** — the old claim's window is closed at the new claim's
  ``effective_from`` (status ``superseded``) and the new claim becomes current,
  chained back by ``supersedes``;
* **authority, new wins** — the old claim is marked ``contradicted`` (retained)
  and the new claim becomes current;
* **authority, old wins** — the old claim stays current and the *new* claim is
  retained as ``contradicted`` (recorded, not applied);
* **escalate** — the old claim stays current, the new claim is held as
  ``contradicted``, and an :class:`Escalation` is emitted for the human approval
  plan with both claims and their provenance.

Every branch retains both claims: an input claim is never deleted and a claim's
``statement`` is never rewritten in place. :func:`assert_no_silent_overwrite`
makes that invariant checkable — the §7.1 "contradiction silently overwritten"
failure mode cannot occur.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from kosha.contradiction.detect import ConflictReport, ContradictionJudge, find_conflict
from kosha.contradiction.policy import Resolution, ResolutionOutcome, resolve_conflict
from kosha.contradiction.temporal import effective_claims
from kosha.model import Claim, ClaimStatus


class SilentOverwriteError(Exception):
    """Raised when reconciliation would drop or rewrite a prior claim."""


@dataclass(frozen=True)
class Escalation:
    """A conflict the policy could not resolve — handed to the human plan."""

    old_claim: Claim
    new_claim: Claim
    rationale: str


@dataclass(frozen=True)
class Reconciliation:
    """The outcome of reconciling one new claim against a concept's claims."""

    claims: tuple[Claim, ...]
    report: ConflictReport
    outcome: ResolutionOutcome | None
    escalation: Escalation | None

    @property
    def conflicting(self) -> bool:
        """Whether a material conflict was detected."""
        return self.report.conflicting

    @property
    def escalated(self) -> bool:
        """Whether the conflict was escalated for human judgment."""
        return self.escalation is not None


def reconcile(
    claims: Sequence[Claim],
    new_claim: Claim,
    *,
    authority: Mapping[str, int],
    judge: ContradictionJudge,
    asof: datetime | None = None,
) -> Reconciliation:
    """Reconcile ``new_claim`` against ``claims``, never losing either claim.

    ``authority`` maps a ``source_id`` to its rank (default 0 when absent). A
    compatible claim is appended as current; a material conflict is resolved by
    the policy and applied so the loser is retained (``superseded`` /
    ``contradicted``) and, when nothing resolves it, escalated.
    """
    in_force = effective_claims(claims, asof=asof)
    report = find_conflict(in_force, new_claim.statement, judge=judge)
    if not report.conflicting:
        return Reconciliation(
            claims=(*claims, new_claim),
            report=report,
            outcome=None,
            escalation=None,
        )

    old = _find(claims, report.old_claim_id)
    old_authority = authority.get(old.source_id, 0)
    new_authority = authority.get(new_claim.source_id, 0)
    outcome = resolve_conflict(
        old, new_claim, old_authority=old_authority, new_authority=new_authority
    )

    if outcome.resolution is Resolution.TEMPORAL:
        updated = _replace(
            claims,
            old.claim_id,
            old.model_copy(
                update={"status": ClaimStatus.SUPERSEDED, "effective_to": new_claim.effective_from}
            ),
        )
        winner = new_claim.model_copy(
            update={"status": ClaimStatus.CURRENT, "supersedes": old.claim_id}
        )
        return Reconciliation((*updated, winner), report, outcome, None)

    if outcome.resolution is Resolution.AUTHORITY and outcome.winner == "new":
        updated = _replace(
            claims, old.claim_id, old.model_copy(update={"status": ClaimStatus.CONTRADICTED})
        )
        winner = new_claim.model_copy(
            update={"status": ClaimStatus.CURRENT, "supersedes": old.claim_id}
        )
        return Reconciliation((*updated, winner), report, outcome, None)

    # Authority keeps the old claim, or the conflict escalates: in both cases the
    # old claim stays current and the new claim is retained as contradicted.
    loser = new_claim.model_copy(update={"status": ClaimStatus.CONTRADICTED})
    escalation = (
        Escalation(old, new_claim, outcome.rationale) if outcome.escalated else None
    )
    return Reconciliation((*claims, loser), report, outcome, escalation)


def assert_no_silent_overwrite(before: Sequence[Claim], after: Sequence[Claim]) -> None:
    """Assert reconciliation neither dropped nor rewrote any prior claim.

    Status and ``effective_to`` may change — that is the explicit, retained
    supersede/expire. A prior claim *disappearing*, or its ``statement`` changing,
    is a silent overwrite and raises :class:`SilentOverwriteError`.
    """
    after_by_id = {claim.claim_id: claim for claim in after}
    for prior in before:
        survivor = after_by_id.get(prior.claim_id)
        if survivor is None:
            raise SilentOverwriteError(f"claim {prior.claim_id!r} was dropped")
        if survivor.statement != prior.statement:
            raise SilentOverwriteError(f"claim {prior.claim_id!r} statement was rewritten in place")


def _find(claims: Sequence[Claim], claim_id: str | None) -> Claim:
    for claim in claims:
        if claim.claim_id == claim_id:
            return claim
    raise KeyError(f"no claim {claim_id!r} in concept")


def _replace(claims: Sequence[Claim], claim_id: str, replacement: Claim) -> list[Claim]:
    return [replacement if claim.claim_id == claim_id else claim for claim in claims]
