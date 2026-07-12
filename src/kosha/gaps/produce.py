"""Deterministic KnowledgeGap event producers (DEVELOPMENT_PLAN.md M10).

Every producer here derives gap *events* purely from already-computed,
deterministic evidence: a bundle's compliance-audit commit history
(:class:`kosha.audit.export.ComplianceReport`, built by
:func:`kosha.audit.export.build_report`). No producer here ever asks a model
a question or invents a gap from free-form text -- each event traces back to
one concrete git commit and the M3/M5 evidence-provenance/coverage fields
that commit's trailers and change records already carry.

An event returned here always has ``status=OPEN``, ``seen_count=1``, and
``opened_at == last_seen_at == at``; merging repeated events from later scans
into one stable, deduplicated gap is :class:`kosha.gaps.ledger.GapLedgerStore`'s
job, not this module's.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from kosha.audit.export import ChangeRecord, CommitRecord, ComplianceReport
from kosha.gaps.model import GapKind, GapReasonCode, KnowledgeGap, dedup_key

_COVERAGE_REASON_CODES: dict[str, GapReasonCode] = {
    "windowed": GapReasonCode.COVERAGE_WINDOWED,
    "cursor_incremental": GapReasonCode.COVERAGE_CURSOR_INCREMENTAL,
    "sampled": GapReasonCode.COVERAGE_SAMPLED,
    "best_effort": GapReasonCode.COVERAGE_BEST_EFFORT,
    "unknown": GapReasonCode.COVERAGE_UNKNOWN,
}


def gaps_from_compliance_report(
    report: ComplianceReport, *, at: datetime
) -> tuple[KnowledgeGap, ...]:
    """Derive one fresh OPEN gap event per deterministic insufficiency signal.

    Two evidenced categories (DEVELOPMENT_PLAN.md M10 entry gate):

    - :attr:`GapKind.LEGACY_EVIDENCE`: an ingest commit whose
      ``evidence_status`` is ``"legacy"`` -- missing a ``Source-Run`` and/or
      ``Evidence-SHA256`` trailer, the same signal
      ``ComplianceReport.legacy_provenance_count`` already counts.
    - :attr:`GapKind.INCOMPLETE_COVERAGE`: a change whose evidence carries a
      non-``"complete"`` :class:`~kosha.evidence.model.SourceCoverage.kind`,
      the same signal ``ComplianceReport.incomplete_coverage_count`` already
      counts.

    One gap event per underlying commit (legacy) or per commit+path
    (incomplete coverage). Duplicates across repeated scans of the same
    history share a stable dedup key (:func:`kosha.gaps.model.dedup_key`), so
    re-running this producer against an unchanged bundle deterministically
    reproduces the same ``gap_id``\\ s.
    """
    events: list[KnowledgeGap] = []
    for commit in report.commits:
        if commit.evidence_status == "legacy":
            events.append(_legacy_evidence_gap(commit, at=at))
        for change in commit.changes:
            if change.coverage is not None and change.coverage != "complete":
                events.append(_incomplete_coverage_gap(commit, change, at=at))
    return tuple(events)


def evidenced_categories(events: Sequence[KnowledgeGap]) -> frozenset[GapKind]:
    """Return the distinct gap kinds actually present in ``events``.

    Used by the DEVELOPMENT_PLAN.md M10 entry gate to prove -- from real
    producer output over real or fixture history, not documentation -- that
    at least two objective categories exist before any lifecycle
    implementation is allowed to ship.
    """
    return frozenset(event.kind for event in events)


def _legacy_evidence_gap(commit: CommitRecord, *, at: datetime) -> KnowledgeGap:
    reason = (
        GapReasonCode.MISSING_SOURCE_RUN_TRAILER
        if commit.source_run is None
        else GapReasonCode.MISSING_EVIDENCE_SHA256
    )
    concept_ids = tuple(sorted({change.path for change in commit.changes}))
    return KnowledgeGap(
        gap_id=dedup_key(GapKind.LEGACY_EVIDENCE, commit.sha),
        kind=GapKind.LEGACY_EVIDENCE,
        reason_code=reason,
        opened_at=at,
        last_seen_at=at,
        affected_concept_ids=concept_ids,
    )


def _incomplete_coverage_gap(
    commit: CommitRecord, change: ChangeRecord, *, at: datetime
) -> KnowledgeGap:
    assert change.coverage is not None  # narrowed by the caller's guard
    reason = _COVERAGE_REASON_CODES.get(change.coverage, GapReasonCode.COVERAGE_UNKNOWN)
    natural_key = f"{commit.sha}:{change.path}"
    return KnowledgeGap(
        gap_id=dedup_key(GapKind.INCOMPLETE_COVERAGE, natural_key),
        kind=GapKind.INCOMPLETE_COVERAGE,
        reason_code=reason,
        opened_at=at,
        last_seen_at=at,
        source_run_ids=(commit.source_run,) if commit.source_run else (),
        evidence_sha256=commit.evidence_sha256,
        affected_concept_ids=(change.path,),
    )
