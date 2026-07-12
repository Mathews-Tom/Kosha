"""Deterministic, evidence-backed knowledge-gap ledger (DEVELOPMENT_PLAN.md M10).

Tracks objectively unresolved knowledge-maintenance conditions -- missing or
legacy evidence provenance, incomplete source coverage -- through an
auditable open/answered/invalidated/stale lifecycle, without ever creating a
model-generated speculative backlog or mutating a claim directly. See
`.docs/DEVELOPMENT_PLAN.md` §5 M10 and
`.docs/memory-and-openwiki-enhancement-plan.md` §17 for the governing
contract.

Gated: this package only exists because committed history already proves at
least two objective gap categories (`kosha.gaps.produce.evidenced_categories`
plus `tests/gaps/test_entry_gate.py`) -- the DEVELOPMENT_PLAN.md M10 entry
gate. A model never invents a gap; every producer in `kosha.gaps.produce`
derives events purely from `kosha.audit.export.ComplianceReport`, the same
deterministic evidence `kosha audit export` already computes.
"""

from __future__ import annotations

from kosha.gaps.ledger import GapLedgerCorruptionError, GapLedgerStore, UnknownGapError
from kosha.gaps.model import GapKind, GapReasonCode, GapStatus, KnowledgeGap, dedup_key
from kosha.gaps.paths import gaps_root, ledger_path
from kosha.gaps.produce import evidenced_categories, gaps_from_compliance_report

__all__ = [
    "GapKind",
    "GapLedgerCorruptionError",
    "GapLedgerStore",
    "GapReasonCode",
    "GapStatus",
    "KnowledgeGap",
    "UnknownGapError",
    "dedup_key",
    "evidenced_categories",
    "gaps_from_compliance_report",
    "gaps_root",
    "ledger_path",
]
