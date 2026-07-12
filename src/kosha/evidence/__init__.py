"""Private, content-addressed evidence vault: immutable source-run contracts.

Persists the exact accepted normalized text extraction consumes, with
deterministic `SourceRun` manifests, restrictive permissions, and fail-loud
corruption handling. See DEVELOPMENT_PLAN.md M2 and
`.docs/memory-and-openwiki-enhancement-plan.md` §9 for the governing
contract. This package defines contracts and one filesystem store only; it is
not wired into the ingest pipeline (that is M3).
"""

from __future__ import annotations

from kosha.evidence.model import EvidenceDocument, RunStatus, SourceRun
from kosha.evidence.paths import (
    InvalidDigestError,
    InvalidRunIdError,
    bundle_identity,
    evidence_root,
    kosha_home,
    validate_digest,
    validate_run_id,
)

__all__ = [
    "EvidenceDocument",
    "InvalidDigestError",
    "InvalidRunIdError",
    "RunStatus",
    "SourceRun",
    "bundle_identity",
    "evidence_root",
    "kosha_home",
    "validate_digest",
    "validate_run_id",
]
