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

from kosha.contradiction.detect import (
    ConflictReport,
    ContradictionJudge,
    ContradictionVerdict,
    DiffSignal,
    GenerationContradictionJudge,
    Judgment,
    LexicalContradictionJudge,
    build_contradiction_prompt,
    detect_conflict,
    find_conflict,
    parse_verdict,
    structured_diff,
)
from kosha.contradiction.escalate import (
    Escalation,
    Reconciliation,
    SilentOverwriteError,
    assert_no_silent_overwrite,
    reconcile,
)
from kosha.contradiction.policy import (
    Resolution,
    ResolutionOutcome,
    Winner,
    resolve_conflict,
)
from kosha.contradiction.temporal import effective_claims, in_force

__all__ = [
    "ConflictReport",
    "ContradictionJudge",
    "ContradictionVerdict",
    "DiffSignal",
    "Escalation",
    "GenerationContradictionJudge",
    "Judgment",
    "LexicalContradictionJudge",
    "Reconciliation",
    "Resolution",
    "ResolutionOutcome",
    "SilentOverwriteError",
    "Winner",
    "assert_no_silent_overwrite",
    "build_contradiction_prompt",
    "detect_conflict",
    "effective_claims",
    "find_conflict",
    "in_force",
    "parse_verdict",
    "reconcile",
    "resolve_conflict",
    "structured_diff",
]
