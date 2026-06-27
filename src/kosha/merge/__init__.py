"""Merge/writer: apply create/update through the claim provenance layer.

The merge milestone (DEVELOPMENT_PLAN M7) writes concept changes by superseding
specific claims rather than rewriting bodies, so fidelity holds across many
sequential ingests (system_design §3, §4.1, §7.1 edit-drift). The body is always
a deterministic projection of the current claims (:func:`render_body`).
"""

from __future__ import annotations

from kosha.merge.claims import (
    current_claims,
    make_claim,
    mint_claim_id,
    render_body,
    supersede_claim,
)

__all__ = [
    "current_claims",
    "make_claim",
    "mint_claim_id",
    "render_body",
    "supersede_claim",
]
