"""Deterministic contradiction-resolution policy (system_design §4.3.1).

Detection is not resolution. Once :mod:`kosha.contradiction.detect` finds a
material conflict, this module decides the winner with a fixed precedence so the
common cases are automatic and only genuine ambiguity reaches a human:

1. **Temporal first.** If the new claim has a later ``effective_from``, it is the
   next policy version: it supersedes, and the old is retained with its window
   closed at the handover date (history preserved, not deleted).
2. **Source-authority next.** Sources carry an ``authority_rank`` (official policy
   doc > wiki page > chat export). Higher authority wins; the loser is marked
   ``contradicted``, not erased.
3. **Escalate the rest.** Equal authority with overlapping validity is genuine
   ambiguity — it goes to the human approval plan with both claims and provenance.

This module is the decision only; applying it to the claim list (closing windows,
marking losers, never deleting) is the escalation/reconcile lane (PR-4).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from kosha.model import Claim

Winner = Literal["new", "old"]


class Resolution(StrEnum):
    """Which rule resolved a conflict (or that it could not be resolved)."""

    TEMPORAL = "temporal"
    AUTHORITY = "authority"
    ESCALATE = "escalate"


@dataclass(frozen=True)
class ResolutionOutcome:
    """The policy's decision for one detected conflict."""

    resolution: Resolution
    winner: Winner | None
    rationale: str

    @property
    def escalated(self) -> bool:
        """Whether the conflict needs human judgment."""
        return self.resolution is Resolution.ESCALATE


def resolve_conflict(
    old: Claim,
    new: Claim,
    *,
    old_authority: int,
    new_authority: int,
) -> ResolutionOutcome:
    """Resolve a detected conflict between ``old`` and ``new`` by fixed precedence.

    Temporal precedence is absolute: a later-effective new claim wins even when the
    old claim carries higher authority, because a dated policy change is a new
    version, not a competing assertion. Authority breaks ties only when neither
    claim is temporally later; equal authority with no temporal ordering escalates.
    """
    if new.effective_from is not None and (
        old.effective_from is None or new.effective_from > old.effective_from
    ):
        return ResolutionOutcome(
            Resolution.TEMPORAL,
            "new",
            f"new effective_from {new.effective_from.isoformat()} supersedes the earlier claim",
        )
    if new_authority != old_authority:
        winner: Winner = "new" if new_authority > old_authority else "old"
        return ResolutionOutcome(
            Resolution.AUTHORITY,
            winner,
            f"source authority {new_authority} vs {old_authority}: {winner} claim wins",
        )
    return ResolutionOutcome(
        Resolution.ESCALATE,
        None,
        f"equal authority ({new_authority}) with overlapping validity; needs human judgment",
    )
