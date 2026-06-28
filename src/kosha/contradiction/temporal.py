"""Claim-level temporal validity: effective dating and the current filter.

system_design §3.2 / §4.3.1. A claim carries an optional validity window
(``effective_from`` .. ``effective_to``); ``effective_to is None`` means the claim
is currently in force. Two readers depend on this window:

* the contradiction-resolution policy (M9) applies the temporal-first rule —
  a later-effective claim supersedes an expired one;
* a consumer answering "what is the policy *now*" filters to the open-ended
  claims (the current view), while "what was it on date X" filters by the window.

:func:`in_force` is that predicate and :func:`effective_claims` is the filter; the
filter composes with the supersede-chain head filter (:func:`current_claims`) so
only in-force, non-retired claims surface.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from kosha.merge.claims import current_claims
from kosha.model import Claim


def in_force(claim: Claim, asof: datetime | None = None) -> bool:
    """Return whether ``claim``'s validity window holds at ``asof``.

    With ``asof=None`` this is the "current" view of system_design §3.2: a claim
    is in force iff it has not been expired (``effective_to is None``). With a
    concrete ``asof`` it is the half-open window check
    ``effective_from <= asof < effective_to``, each bound treated as open when its
    field is unset.
    """
    if asof is None:
        return claim.effective_to is None
    after_start = claim.effective_from is None or asof >= claim.effective_from
    before_end = claim.effective_to is None or asof < claim.effective_to
    return after_start and before_end


def effective_claims(
    claims: Sequence[Claim], *, asof: datetime | None = None
) -> list[Claim]:
    """Return the in-force current claims: supersede heads valid at ``asof``.

    The temporal "current filter". It first drops retired (superseded /
    contradicted) chains via :func:`current_claims`, then keeps only those whose
    validity window holds at ``asof`` — by default the open-ended ones, the
    "current" view a consumer answers from.
    """
    return [claim for claim in current_claims(claims) if in_force(claim, asof)]
