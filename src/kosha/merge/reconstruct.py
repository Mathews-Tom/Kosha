"""Edit-drift guard: reconstruct a concept from its cited sources (M7 PR-4).

The §7.1 edit-drift failure mode is repeated LLM body rewrites losing fidelity
across ingests. Two invariants close it, both checked here:

1. **No freehand body.** The on-disk body must equal the deterministic
   projection of the concept's claims (:func:`assert_no_drift`). A body that
   differs has been edited outside the claim layer.
2. **Every live claim is grounded.** Each in-force claim's statement must be
   recoverable from the source it cites (:func:`reconstruct_from_sources`); a
   claim absent from its source is an unprovenanced edit, not a real assertion.

Together they make a concept *reconstructable from its cited sources*: rebuild
the body from the claims, having proven each claim traces back to a source.
"""

from __future__ import annotations

from collections.abc import Mapping

from kosha.merge.claims import current_claims, render_body
from kosha.model import Claim, Concept


class EditDriftError(Exception):
    """A concept body or claim set has drifted from its cited sources."""


def assert_no_drift(concept: Concept) -> None:
    """Raise if the body is not the exact projection of the concept's claims."""
    expected = render_body(concept.claims)
    if concept.body != expected:
        raise EditDriftError(
            f"body of {concept.concept_id!r} drifted from its claim projection"
        )


def ungrounded_claims(concept: Concept, sources: Mapping[str, str]) -> list[Claim]:
    """Return the in-force claims whose statement is absent from its cited source.

    ``sources`` maps a ``source_id`` to the source's normalized text. Only
    current claims are checked — a superseded claim is retained history whose
    source may no longer be on hand.
    """
    missing: list[Claim] = []
    for claim in current_claims(concept.claims):
        text = sources.get(claim.source_id)
        if text is None or _normalize(claim.statement) not in _normalize(text):
            missing.append(claim)
    return missing


def is_reconstructable(concept: Concept, sources: Mapping[str, str]) -> bool:
    """True when every in-force claim is recoverable from its cited source."""
    return not ungrounded_claims(concept, sources)


def reconstruct_from_sources(concept: Concept, sources: Mapping[str, str]) -> str:
    """Rebuild the concept body from its claims, proving each traces to a source.

    Raises :class:`EditDriftError` listing any in-force claim not grounded in its
    cited source; otherwise returns the reconstructed body (the claim projection).
    """
    missing = ungrounded_claims(concept, sources)
    if missing:
        ids = ", ".join(claim.claim_id for claim in missing)
        raise EditDriftError(
            f"{concept.concept_id!r} not reconstructable: ungrounded claim(s) {ids}"
        )
    return render_body(concept.claims)


def _normalize(text: str) -> str:
    """Collapse runs of whitespace so layout differences don't defeat grounding."""
    return " ".join(text.split())
