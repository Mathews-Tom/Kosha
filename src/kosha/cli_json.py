"""Structured (``--json``) result payloads for CLI commands (M8 PR-1).

Every subcommand already renders a human-readable text report from a typed
result object (``Report``, ``BenchReport``, ``IngestResult``, ...). This module
builds the same information as a JSON-serializable ``dict`` instead, so CI and
other scripted consumers can parse a command's outcome without scraping stdout.

Payloads are hand-curated per command rather than a blind ``dataclasses.asdict``
dump: several result types expose their most useful numbers (precision, recall,
accuracy, ...) as computed properties that ``asdict`` would silently drop, and
``kosha ingest``'s plan/routing carries full file *content* that the text
renderer never prints — the JSON payload stays a structured mirror of the text
output, not a raw internal-object dump, so it does not leak more than the
existing surface already does.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from kosha.bench import (
    BenchReport,
    Calibration,
    DedupSignal,
    KillSignal,
    SingleThresholdCalibration,
)
from kosha.bench.acceptance import AcceptanceReport
from kosha.bench.realworld import RealworldReport
from kosha.connectors import ConnectorState, SourceInstance, SourceRunReport
from kosha.eval import (
    ContradictEvalReport,
    DedupEvalReport,
    DuplicateRateReport,
    ExtractEvalReport,
    MergeEvalReport,
    RelateEvalReport,
)
from kosha.evidence.model import SourceRun
from kosha.evidence.replay import ReplayReport
from kosha.evidence.verify import VerificationReport
from kosha.gaps.model import KnowledgeGap
from kosha.pipeline import IngestResult
from kosha.recovery import BackupTag, RecoveryRecord, ReindexPlan, RestorePlan
from kosha.release import ReleaseRecord
from kosha.validate import Report


def dumps(payload: dict[str, Any]) -> str:
    """Render a CLI JSON payload as a stable, human-diffable string."""
    return json.dumps(payload, indent=2)


def validate_json(bundle: Path, report: Report) -> dict[str, Any]:
    """Structured ``kosha validate --json`` result."""
    return {
        "bundle": str(bundle),
        "conformant": report.ok,
        "error_count": len(report.errors),
        "warning_count": len(report.warnings),
        "findings": [
            {
                "severity": finding.severity.value,
                "path": finding.path,
                "rule": finding.rule.value,
                "message": finding.message,
            }
            for finding in report.findings
        ],
    }


def bench_json(
    bundle_path: Path,
    report: BenchReport,
    dedup: DedupSignal,
    kill_signals: list[KillSignal],
    verdict: str,
) -> dict[str, Any]:
    """Structured ``kosha bench --json`` result."""
    return {
        "bundle": str(bundle_path),
        "embedding_provider": report.embedding_provider,
        "generation_provider": report.generation_provider,
        "query_count": report.query_count,
        "strategies": [
            {
                "name": result.name,
                "avg_context_tokens": result.avg_context_tokens,
                "avg_total_tokens": result.avg_total_tokens,
                "avg_round_trips": result.avg_round_trips,
                "avg_latency_ms": result.avg_latency_ms,
                "concept_recall": result.concept_recall,
                "keyword_recall": result.keyword_recall,
                "answered_fraction": result.answered_fraction,
            }
            for result in report.results
        ],
        "dedup_threshold_accuracy": dedup.best_accuracy,
        "kill_signals": [
            {
                "id": signal.id,
                "fired": signal.fired,
                "verdict": signal.verdict,
                "evidence": signal.evidence,
            }
            for signal in kill_signals
        ],
        "verdict": verdict,
    }


def bench_acceptance_json(bundle_path: Path, report: AcceptanceReport) -> dict[str, Any]:
    """Structured ``kosha bench acceptance --json`` result."""
    return {
        "bundle": str(bundle_path),
        "concept_count": report.concept_count,
        "embedding_provider": report.embedding_provider,
        "generation_provider": report.generation_provider,
        "criteria": [
            {
                "id": criterion.id,
                "name": criterion.name,
                "passed": criterion.passed,
                "target": criterion.target,
                "evidence": criterion.evidence,
            }
            for criterion in report.criteria
        ],
        "passed": report.passed,
    }


def bench_realworld_json(corpus_path: Path, report: RealworldReport) -> dict[str, Any]:
    """Structured ``kosha bench realworld --json`` result."""
    return {
        "corpus": str(corpus_path),
        "embedding_provider": report.embedding_provider,
        "generation_provider": report.generation_provider,
        "concept_count": report.concept_count,
        "query_count": report.query_count,
        "maintenance": [
            {
                "name": result.name,
                "correct": result.correct,
                "total": result.total,
                "accuracy": result.accuracy,
                "by_kind": result.by_kind,
            }
            for result in report.maintenance
        ],
        "maintenance_delta": report.maintenance_delta,
        "safety": [
            {
                "name": result.name,
                "cases": result.cases,
                "safe": result.safe,
                "silent_overwrites": result.silent_overwrites,
                "safety_rate": result.safety_rate,
            }
            for result in report.safety
        ],
        "safety_delta": report.safety_delta,
        "drift": {
            "ingests": report.drift.ingests,
            "accuracy_start": report.drift.accuracy_start,
            "accuracy_end": report.drift.accuracy_end,
            "fidelity_ok": report.drift.fidelity_ok,
            "fidelity_targeter": report.drift.fidelity_targeter,
            "seed_concepts": report.drift.seed_concepts,
            "final_concepts": report.drift.final_concepts,
            "grew": report.drift.grew,
        },
        "verdict": report.verdict,
    }


def _single_threshold_json(calibration: SingleThresholdCalibration) -> dict[str, Any]:
    return {
        "surface": calibration.surface,
        "threshold": calibration.threshold,
        "case_count": calibration.case_count,
        "positive_count": calibration.positive_count,
        "negative_count": calibration.negative_count,
        "fit_score": calibration.fit_score,
    }


def calibrate_json(
    calibration: Calibration,
    adjudicator: SingleThresholdCalibration,
    targeter: SingleThresholdCalibration,
    relator: SingleThresholdCalibration,
) -> dict[str, Any]:
    """Structured ``kosha calibrate --json`` result."""
    return {
        "embedding": {
            "provider": calibration.provider,
            "pair_count": calibration.pair_count,
            "high": calibration.thresholds.high,
            "low": calibration.thresholds.low,
            "overlapping": calibration.overlapping,
        },
        "adjudicator": _single_threshold_json(adjudicator),
        "targeter": _single_threshold_json(targeter),
        "relator": _single_threshold_json(relator),
    }


def eval_extract_json(
    labels_path: Path, provider_name: str, report: ExtractEvalReport
) -> dict[str, Any]:
    """Structured ``kosha eval extract --json`` result."""
    return {
        "labels": str(labels_path),
        "generation_provider": provider_name,
        "label_count": report.label_count,
        "correct": report.correct,
        "score": report.score,
    }


def eval_dedup_json(
    labels_path: Path,
    bundle_path: Path,
    embedding_provider_name: str,
    adjudicator_name: str,
    report: DedupEvalReport,
    duplicates: DuplicateRateReport,
) -> dict[str, Any]:
    """Structured ``kosha eval dedup --json`` result."""
    return {
        "labels": str(labels_path),
        "bundle": str(bundle_path),
        "embedding_provider": embedding_provider_name,
        "adjudicator": adjudicator_name,
        "pair_count": report.pair_count,
        "precision": report.precision,
        "recall": report.recall,
        "accuracy": report.accuracy,
        "duplicate_rate": {
            "concept_count": duplicates.concept_count,
            "created": duplicates.created,
            "updated": duplicates.updated,
            "rate": duplicates.duplicate_rate,
        },
    }


def eval_merge_json(
    labels_path: Path, targeter_name: str, report: MergeEvalReport
) -> dict[str, Any]:
    """Structured ``kosha eval merge --json`` result."""
    return {
        "labels": str(labels_path),
        "targeter": targeter_name,
        "case_count": report.case_count,
        "correct": report.correct,
        "score": report.score,
    }


def eval_relate_json(
    labels_path: Path, relator_name: str, report: RelateEvalReport
) -> dict[str, Any]:
    """Structured ``kosha eval relate --json`` result."""
    return {
        "labels": str(labels_path),
        "relator": relator_name,
        "case_count": report.case_count,
        "true_positives": report.true_positives,
        "predicted": report.predicted,
        "gold_total": report.gold_total,
        "precision": report.precision,
        "recall": report.recall,
        "f1": report.f1,
    }


def eval_contradict_json(
    labels_path: Path,
    judge_name: str,
    report: ContradictEvalReport,
    by_regime: dict[str, ContradictEvalReport],
) -> dict[str, Any]:
    """Structured ``kosha eval contradict --json`` result."""
    return {
        "labels": str(labels_path),
        "judge": judge_name,
        "case_count": report.case_count,
        "precision": report.precision,
        "recall": report.recall,
        "f1": report.f1,
        "accuracy": report.accuracy,
        "by_regime": {
            regime: {
                "case_count": regime_report.case_count,
                "precision": regime_report.precision,
                "recall": regime_report.recall,
                "f1": regime_report.f1,
            }
            for regime, regime_report in by_regime.items()
        },
    }


def ingest_json(result: IngestResult, *, dry_run: bool) -> dict[str, Any]:
    """Structured ``kosha ingest --json`` result.

    File *content* is deliberately omitted — the text renderer never prints it
    either, and the same content is already durable in the commit itself once
    approved.
    """
    return {
        "dry_run": dry_run,
        "decision": result.decision.value if result.decision is not None else None,
        "committed": result.committed,
        "branch": result.branch,
        "commit_sha": result.commit_sha,
        "backup_tag": result.backup_tag,
        "reviewer": result.reviewer,
        "plan": {
            "change_count": len(result.plan.changes),
            "flag_count": len(result.plan.flags),
            "changes": [
                {
                    "path": change.path,
                    "kind": change.kind.value,
                    "summary": change.summary,
                    "concept_id": change.concept_id,
                    "confidence": change.confidence,
                    "impact": change.impact.value,
                    "contradiction": change.contradiction.value,
                    "coverage": (
                        change.coverage.model_dump(mode="json")
                        if change.coverage is not None
                        else None
                    ),
                }
                for change in result.plan.changes
            ],
            "flags": [
                {"concept_id": flag.concept_id, "summary": flag.summary, "detail": flag.detail}
                for flag in result.plan.flags
            ],
        },
        "routing": {
            "lane": result.routing.lane.label,
            "requires_approval": result.routing.requires_approval,
            "routes": [
                {"path": route.change.path, "lane": route.lane.label, "reason": route.reason}
                for route in result.routing.routes
            ],
        },
    }


def recover_backups_json(bundle: Path, backups: list[BackupTag]) -> dict[str, Any]:
    """Structured ``kosha recover backups --json`` result."""
    return {
        "bundle": str(bundle),
        "backups": [{"name": b.name, "sha": b.sha, "date": b.date} for b in backups],
    }


def recover_restore_json(
    bundle: Path, plan: RestorePlan, record: RecoveryRecord | None
) -> dict[str, Any]:
    """Structured ``kosha recover restore --json`` result."""
    return {
        "bundle": str(bundle),
        "tag": plan.tag,
        "ref": plan.ref,
        "changes": [{"status": c.status, "path": c.path} for c in plan.changes],
        "applied": record.applied if record is not None else False,
        "record": to_recovery_json(record) if record is not None else None,
    }


def recover_reindex_json(
    bundle: Path, plan: ReindexPlan, record: RecoveryRecord | None
) -> dict[str, Any]:
    """Structured ``kosha recover reindex --json`` result."""
    return {
        "bundle": str(bundle),
        "changes": [{"action": c.action, "path": c.path} for c in plan.changes],
        "applied": record.applied if record is not None else False,
        "record": to_recovery_json(record) if record is not None else None,
    }


def to_recovery_json(record: RecoveryRecord) -> dict[str, Any]:
    """Structured view of a :class:`~kosha.recovery.RecoveryRecord`."""
    return {
        "action": record.action,
        "applied": record.applied,
        "timestamp": record.timestamp,
        "backup_tag": record.backup_tag,
        "branch": record.branch,
        "commit_sha": record.commit_sha,
        "paths": list(record.paths),
        "source_ref": record.source_ref,
    }


def release_json(bundle: Path, record: ReleaseRecord) -> dict[str, Any]:
    """Structured ``kosha release --json`` result."""
    return {
        "bundle": str(bundle),
        "tag": record.tag,
        "ref": record.ref,
        "timestamp": record.timestamp,
        "concept_count": record.concept_count,
        "warning_count": record.warning_count,
        "export_path": record.export_path,
    }


def evidence_verify_json(report: VerificationReport) -> dict[str, Any]:
    """Structured ``kosha evidence verify --json`` result."""
    return {
        "bundle_root": report.bundle_root,
        "evidence_root": report.evidence_root,
        "ref": report.ref,
        "ok": report.ok,
        "run_count": len(report.runs),
        "corrupt_run_count": report.corrupt_run_count,
        "commit_count": len(report.commits),
        "unresolved_commit_count": report.unresolved_commit_count,
        "legacy_commit_count": report.legacy_commit_count,
        "runs": [
            {
                "run_id": run.run_id,
                "ok": run.ok,
                "evidence_object_count": run.evidence_object_count,
                "error": run.error,
            }
            for run in report.runs
        ],
        "commits": [
            {
                "sha": commit.sha,
                "source_run": commit.source_run,
                "evidence_sha256": list(commit.evidence_sha256),
                "ok": commit.ok,
                "error": commit.error,
            }
            for commit in report.commits
        ],
    }


def evidence_show_json(run: SourceRun, texts: Mapping[str, str] | None) -> dict[str, Any]:
    """Structured ``kosha evidence show --json`` result.

    ``texts`` is ``None`` unless ``--content`` was explicit; the payload never
    includes a document's normalized text otherwise.
    """
    return {
        "run_id": run.run_id,
        "bundle_identity": run.bundle_identity,
        "source_instance_id": run.source_instance_id,
        "adapter": run.adapter,
        "adapter_version": run.adapter_version,
        "started_at": run.started_at.isoformat(),
        "completed_at": run.completed_at.isoformat(),
        "status": run.status.value,
        "detector_names": list(run.detector_names),
        "warnings": list(run.warnings),
        "coverage": run.coverage.model_dump(mode="json"),
        "evidence": [
            {
                "sha256": document.sha256,
                "source_id": document.source_id,
                "location": document.location,
                "retrieved_at": (
                    document.retrieved_at.isoformat() if document.retrieved_at else None
                ),
                "media_type": document.media_type,
                "normalized_text_bytes": document.normalized_text_bytes,
                "normalization_version": document.normalization_version,
                **({"text": texts[document.sha256]} if texts is not None else {}),
            }
            for document in run.evidence
        ],
    }


def evidence_replay_json(report: ReplayReport) -> dict[str, Any]:
    """Structured ``kosha evidence replay --json`` result."""
    return {
        "run_id": report.run_id,
        "bundle_root": report.bundle_root,
        "original_pipeline": {
            "adapter": report.original.adapter,
            "adapter_version": report.original.adapter_version,
            "normalization_versions": list(report.original.normalization_versions),
        },
        "current_pipeline": {
            "adapter": report.current.adapter,
            "adapter_version": report.current.adapter_version,
            "normalization_versions": list(report.current.normalization_versions),
        },
        "pipeline_identity_changed": report.pipeline_identity_changed,
        "current_providers": {
            "embedding": report.current.embedding_provider,
            "generation": report.current.generation_provider,
        },
        "original_provider_identity_recorded": False,
        "replay_paths": list(report.replay_paths),
        "original_commit": (
            {"sha": report.original_commit_sha, "paths": list(report.original_paths)}
            if report.original_commit_sha is not None
            else None
        ),
        "path_differences": {
            "added": list(report.added_paths),
            "removed": list(report.removed_paths),
        },
    }


def source_list_json(instances: Sequence[SourceInstance]) -> dict[str, Any]:
    """Structured ``kosha source list --json`` result."""
    return {
        "instances": [
            {
                "instance_id": instance.instance_id,
                "connector_id": instance.connector_id,
                "enabled": instance.enabled,
                "schedule": instance.schedule,
            }
            for instance in instances
        ]
    }


def source_status_json(instance: SourceInstance, state: ConnectorState | None) -> dict[str, Any]:
    """Structured ``kosha source status --json`` result.

    ``state`` is ``None`` when the instance has never run -- reported
    honestly as ``null`` rather than a fabricated empty state.
    """
    return {
        "instance_id": instance.instance_id,
        "connector_id": instance.connector_id,
        "enabled": instance.enabled,
        "schedule": instance.schedule,
        "state": state.model_dump(mode="json") if state is not None else None,
    }


def source_run_json(report: SourceRunReport) -> dict[str, Any]:
    """Structured ``kosha source run --json`` result."""
    result = report.ingest_result
    return {
        "instance_id": report.instance_id,
        "run_id": report.run_id,
        "outcome": report.outcome.value,
        "message": report.message,
        "committed": result.committed if result is not None else False,
        "commit_sha": result.commit_sha if result is not None else None,
        "branch": result.branch if result is not None else None,
        "state": report.state.model_dump(mode="json"),
    }



def gap_json(gap: KnowledgeGap) -> dict[str, Any]:
    """Structured view of one :class:`~kosha.gaps.model.KnowledgeGap`."""
    return gap.model_dump(mode="json")


def gap_scan_json(events: Sequence[KnowledgeGap], merged: Sequence[KnowledgeGap]) -> dict[str, Any]:
    """Structured ``kosha gap scan --json`` result.

    ``events`` is this scan's fresh producer output before merging;
    ``merged`` is the full post-merge ledger, so a caller can see both what
    this scan observed and the ledger's resulting state.
    """
    return {
        "scanned_events": len(events),
        "categories": sorted({event.kind.value for event in events}),
        "ledger": [gap_json(gap) for gap in merged],
    }


def gap_list_json(gaps: Sequence[KnowledgeGap]) -> dict[str, Any]:
    """Structured ``kosha gap list --json`` result."""
    return {"gaps": [gap_json(gap) for gap in gaps]}


def gap_show_json(gap: KnowledgeGap) -> dict[str, Any]:
    """Structured ``kosha gap show --json`` result."""
    return gap_json(gap)


def gap_transition_json(gap: KnowledgeGap) -> dict[str, Any]:
    """Structured ``kosha gap answer|invalidate|stale --json`` result."""
    return gap_json(gap)