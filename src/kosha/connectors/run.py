"""Connector run orchestration: transactional cursor advancement (DEVELOPMENT_PLAN.md M6).

:func:`run_source_instance` is the one place a source instance's cursor ever
moves. State advances only after a run's evidence has actually been
persisted (``result.committed`` -- the one point
``kosha.pipeline.run.commit_plan`` calls ``persist_evidence_run``, see
``kosha.pipeline.run.ingest``): a raised exception, a rejected plan, an
empty plan, or a dry run all leave the prior cursor exactly where it was
(enhancement plan §13).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from kosha.approve import Decision, Reader
from kosha.connectors.config import resolve_connector
from kosha.connectors.model import (
    ConnectorRunContext,
    ConnectorState,
    RunSummary,
    SourceInstance,
    SourceRunOutcome,
)
from kosha.connectors.state import ConnectorStateStore
from kosha.evidence import EvidenceStore, evidence_root
from kosha.pipeline import IngestResult
from kosha.security.secret_scan import scan_text

_MAX_MESSAGE_CHARS = 500


@dataclass(frozen=True)
class SourceRunReport:
    """What ``kosha source run`` reports back to its caller."""

    instance_id: str
    run_id: str
    outcome: SourceRunOutcome
    message: str
    ingest_result: IngestResult | None
    state: ConnectorState


def run_source_instance(
    instance: SourceInstance,
    *,
    bundle_root: Path,
    state_store: ConnectorStateStore,
    evidence_store: EvidenceStore | None = None,
    asof: datetime | None = None,
    dry_run: bool = False,
    assume_yes: bool = False,
    reader: Reader | None = None,
    reviewer: str | None = None,
) -> SourceRunReport:
    """Run ``instance`` once, advancing its cursor only on a persisted success.

    Loads prior state first (failing loud if it is present but malformed --
    see :meth:`~kosha.connectors.state.ConnectorStateStore.load`, never
    silently resetting to a fresh cursor), resolves the instance's connector
    from the explicit registry (failing loud on an unknown ``connector_id``),
    then runs its ingest function. Any exception the connector raises --
    network failure, guardrail rejection, lock contention -- is caught here
    and recorded as a FAILED run rather than propagating, so one bad attempt
    never crashes the CLI mid-run; the prior cursor is left untouched either
    way. A clean run that did not commit (human rejection, an empty plan, or
    an explicit dry run) is recorded as REJECTED, also without touching the
    cursor. Only a committed run -- meaning its evidence was actually
    persisted -- advances ``cursor``/``last_success_*`` and is recorded as
    SUCCESS.
    """
    definition = resolve_connector(instance.connector_id)
    started_at = asof or datetime.now(UTC)
    run_id = uuid4().hex
    default_state = ConnectorState(instance_id=instance.instance_id)
    prior = state_store.load(instance.instance_id) or default_state
    vault = evidence_store or EvidenceStore(evidence_root(bundle_root))
    context = ConnectorRunContext(
        instance=instance,
        bundle_root=bundle_root,
        asof=started_at,
        cursor=prior.cursor,
        evidence_store=vault,
        dry_run=dry_run,
        assume_yes=assume_yes,
        reviewer=reviewer,
        reader=reader,
    )
    try:
        result = definition.ingest(context)
    except Exception as exc:  # every adapter failure becomes a FAILED run record, not a crash
        summary = RunSummary(
            run_id=run_id,
            status=SourceRunOutcome.FAILED,
            started_at=started_at,
            completed_at=started_at,
            message=_safe_message(str(exc)),
        )
        new_state = prior.record_attempt(summary)
        state_store.save(new_state)
        return SourceRunReport(
            instance.instance_id, run_id, SourceRunOutcome.FAILED, summary.message, None, new_state
        )

    completed_at = started_at
    if dry_run or not result.committed:
        message = _describe_uncommitted(result, dry_run=dry_run)
        summary = RunSummary(
            run_id=run_id,
            status=SourceRunOutcome.REJECTED,
            started_at=started_at,
            completed_at=completed_at,
            message=message,
        )
        new_state = prior.record_attempt(summary)
        state_store.save(new_state)
        return SourceRunReport(
            instance.instance_id, run_id, SourceRunOutcome.REJECTED, message, result, new_state
        )

    message = f"committed {result.commit_sha or ''} on {result.branch or ''}".strip()
    summary = RunSummary(
        run_id=run_id,
        status=SourceRunOutcome.SUCCESS,
        started_at=started_at,
        completed_at=completed_at,
        message=message,
    )
    new_cursor = prior.cursor
    coverage_cursor = (
        result.evidence_run.run.coverage.cursor_after if result.evidence_run is not None else None
    )
    if coverage_cursor is not None:
        new_cursor = coverage_cursor
    new_state = prior.advance(summary, cursor=new_cursor)
    state_store.save(new_state)
    return SourceRunReport(
        instance.instance_id, run_id, SourceRunOutcome.SUCCESS, message, result, new_state
    )


def _describe_uncommitted(result: IngestResult, *, dry_run: bool) -> str:
    if dry_run:
        return "dry run: plan not committed"
    if result.decision is Decision.REJECT:
        return "rejected: approval declined"
    if result.plan.is_empty:
        return "no changes: nothing to commit"
    if result.evidence_run is not None and result.evidence_run.run.status.value == "rejected":
        detectors = ", ".join(result.evidence_run.run.detector_names) or "unknown"
        return f"evidence rejected: detector(s) {detectors}"
    return "not committed"


def _safe_message(text: str) -> str:
    """Truncate and withhold ``text`` if it looks credential-shaped.

    An adapter exception's message can echo raw request context (a URL with
    an operator-embedded query parameter, a filesystem path); this is the
    same guard :class:`~kosha.connectors.model.RunSummary` enforces on
    construction, applied first so a message that would fail validation is
    replaced with a safe placeholder instead of raising out of the run loop.
    """
    trimmed = " ".join(text.split())[:_MAX_MESSAGE_CHARS]
    if scan_text(trimmed):
        return "run failed: diagnostic message withheld (matched a secret detector)"
    return trimmed
