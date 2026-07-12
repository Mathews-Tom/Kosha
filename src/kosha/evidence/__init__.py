"""Private, content-addressed evidence vault: immutable source-run contracts.

Persists the exact accepted normalized text extraction consumes, with
deterministic `SourceRun` manifests, restrictive permissions, and fail-loud
corruption handling. See DEVELOPMENT_PLAN.md M2 and
`.docs/memory-and-openwiki-enhancement-plan.md` §9 for the governing
contract. `kosha.pipeline.run.ingest` wires this vault into the maintenance
loop (M3); `kosha.evidence.verify` and `kosha.evidence.replay` (M4) verify
and replay stored runs -- import them directly rather than through this
package, since both pull in `kosha.pipeline`, which itself imports this
package.
"""

from __future__ import annotations

from kosha.evidence.model import (
    CoverageKind,
    EvidenceDocument,
    RunStatus,
    SourceCoverage,
    SourceRun,
    hash_evidence_text,
)
from kosha.evidence.paths import (
    InvalidDigestError,
    InvalidRunIdError,
    bundle_identity,
    evidence_root,
    kosha_home,
    validate_digest,
    validate_run_id,
)
from kosha.evidence.store import EvidenceConflictError, EvidenceCorruptionError, EvidenceStore

__all__ = [
    "CoverageKind",
    "EvidenceConflictError",
    "EvidenceCorruptionError",
    "EvidenceDocument",
    "EvidenceStore",
    "InvalidDigestError",
    "InvalidRunIdError",
    "RunStatus",
    "SourceCoverage",
    "SourceRun",
    "bundle_identity",
    "evidence_root",
    "hash_evidence_text",
    "kosha_home",
    "validate_digest",
    "validate_run_id",
]
