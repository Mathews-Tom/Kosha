"""Contradiction detection, resolution policy, and temporal validity (M9).

The maintenance loop must never silently overwrite knowledge (system_design
§4.3.1, §7.1). This package detects material conflicts between a new claim and the
prior in-force claims of a concept, then resolves them deterministically —
temporal-first (a later-effective claim supersedes an expired one), then
source-authority (higher rank wins), then escalates the residue to the human
approval plan. Losers are retained (marked ``superseded`` / ``contradicted``),
never deleted, so a concept carries its history rather than forking files.
"""

from __future__ import annotations

from kosha.contradiction.temporal import effective_claims, in_force

__all__ = [
    "effective_claims",
    "in_force",
]
