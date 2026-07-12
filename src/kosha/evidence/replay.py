"""Replay a stored source run through the current pipeline as a zero-network dry run.

:func:`replay_run` never fetches a source: it reads the exact stored evidence
bytes (:meth:`~kosha.evidence.store.EvidenceStore.read_object`), reconstructs
:class:`~kosha.model.RawDoc` objects from them, and feeds them straight into
:func:`kosha.pipeline.ingest` with ``dry_run=True`` -- the same pure plan-build
path a live ingest takes before the approve gate, just fed frozen text instead
of a live read. The embedding/generation providers are always the
deterministic local ones (:class:`~kosha.providers.lexical.LexicalEmbeddingProvider`,
:class:`~kosha.providers.extractive.ExtractiveGenerationProvider`), never the
env-resolved providers :mod:`kosha.providers.factory` would pick: an
operator's ambient ``KOSHA_GEN_BASE_URL`` must never turn a replay into a live
network call (DEVELOPMENT_PLAN.md M4; enhancement plan §11).

A run's stored ``adapter_version`` / evidence ``normalization_version`` are
compared against the pipeline's *current* constants and reported as
original-vs-current pipeline identity; the current (offline) embedding and
generation provider names are reported too. No *original* provider identity
is reported, because no pre-M4 run ever recorded one -- this module never
fabricates or emulates one (``no historical provider emulation``). Where the
run's original commit is still reachable in git history, the replayed plan's
paths are diffed against what that commit actually wrote and any mismatch is
labeled a replay difference, not corruption.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from kosha.audit.export import build_report
from kosha.evidence.model import RunStatus, SourceRun
from kosha.evidence.paths import evidence_root
from kosha.evidence.store import EvidenceStore
from kosha.ingest.guardrails import ADAPTER_VERSION, EVIDENCE_NORMALIZATION_VERSION
from kosha.model import RawDoc, Source, SourceKind
from kosha.pipeline import ingest
from kosha.providers.extractive import ExtractiveGenerationProvider
from kosha.providers.lexical import LexicalEmbeddingProvider


class ReplayError(RuntimeError):
    """Raised when a stored run carries no evidence to replay (rejected/failed)."""


@dataclass(frozen=True)
class PipelineIdentity:
    """One pipeline/provider identity snapshot -- original (stored) or current (live)."""

    adapter: str
    adapter_version: str
    normalization_versions: tuple[str, ...]
    embedding_provider: str | None = None
    generation_provider: str | None = None


@dataclass(frozen=True)
class ReplayReport:
    """The outcome of replaying one stored source run through the current pipeline."""

    run_id: str
    bundle_root: str
    original: PipelineIdentity
    current: PipelineIdentity
    replay_paths: tuple[str, ...]
    original_commit_sha: str | None
    original_paths: tuple[str, ...]
    added_paths: tuple[str, ...]
    removed_paths: tuple[str, ...]

    @property
    def pipeline_identity_changed(self) -> bool:
        """True when the current pipeline's version identity drifted from the original run."""
        return self.original.adapter_version != self.current.adapter_version or set(
            self.original.normalization_versions
        ) != set(self.current.normalization_versions)


@dataclass(frozen=True)
class _OriginalCommit:
    sha: str
    paths: tuple[str, ...]


def replay_run(
    bundle_root: Path,
    run_id: str,
    *,
    store: EvidenceStore | None = None,
    asof: datetime | None = None,
    ref: str = "HEAD",
) -> ReplayReport:
    """Replay ``run_id`` through the current pipeline, producing a zero-network dry-run plan.

    Raises :class:`~kosha.evidence.store.EvidenceCorruptionError` on a missing
    or malformed manifest/object (never substituted with a live refetch) and
    :class:`ReplayError` when the run is not ``accepted`` -- a rejected or
    failed run carries no stored body, so there is nothing to replay.
    """
    vault = store or EvidenceStore(evidence_root(bundle_root))
    run = vault.read_run(run_id)
    if run.status is not RunStatus.ACCEPTED:
        raise ReplayError(
            f"source run {run_id!r} is {run.status.value}: no evidence to replay "
            "(only an accepted run carries a stored body)"
        )
    raw_docs = _reconstruct_raw_docs(vault, run)
    embedder = LexicalEmbeddingProvider()
    generator = ExtractiveGenerationProvider()
    result = ingest(
        Path(run.source_instance_id),
        bundle_root,
        asof=asof or datetime.now(UTC),
        dry_run=True,
        raw_docs=raw_docs,
        embedding_provider=embedder,
        generation_provider=generator,
    )
    original = PipelineIdentity(
        adapter=run.adapter,
        adapter_version=run.adapter_version,
        normalization_versions=tuple(sorted({doc.normalization_version for doc in run.evidence})),
    )
    current = PipelineIdentity(
        adapter=run.adapter,
        adapter_version=ADAPTER_VERSION,
        normalization_versions=(EVIDENCE_NORMALIZATION_VERSION,),
        embedding_provider=embedder.name,
        generation_provider=generator.name,
    )
    original_commit = _find_original_commit(bundle_root, run_id, ref)
    replay_paths = tuple(result.plan.paths())
    original_paths = original_commit.paths if original_commit is not None else ()
    return ReplayReport(
        run_id=run_id,
        bundle_root=str(bundle_root),
        original=original,
        current=current,
        replay_paths=replay_paths,
        original_commit_sha=original_commit.sha if original_commit is not None else None,
        original_paths=original_paths,
        added_paths=tuple(sorted(set(replay_paths) - set(original_paths))),
        removed_paths=tuple(sorted(set(original_paths) - set(replay_paths))),
    )


def _reconstruct_raw_docs(vault: EvidenceStore, run: SourceRun) -> list[RawDoc]:
    """Reconstruct RawDocs from ``run``'s stored evidence -- no filesystem/network read."""
    kind = SourceKind(run.adapter)
    docs: list[RawDoc] = []
    for document in run.evidence:
        text = vault.read_object(document.sha256)  # exact stored bytes -- never a live refetch
        source = Source(
            source_id=document.source_id,
            kind=kind,
            location=document.location,
            retrieved_at=document.retrieved_at,
        )
        docs.append(
            RawDoc(
                source=source,
                text=text,
                source_run_id=run.run_id,
                evidence_sha256=document.sha256,
            )
        )
    return docs


def _find_original_commit(bundle_root: Path, run_id: str, ref: str) -> _OriginalCommit | None:
    report = build_report(bundle_root, ref=ref)
    for commit in report.commits:
        if commit.source_run == run_id:
            return _OriginalCommit(
                sha=commit.sha, paths=tuple(sorted(change.path for change in commit.changes))
            )
    return None


def render_replay_text(report: ReplayReport) -> str:
    """Render ``report`` as a human-readable zero-network replay summary."""
    lines = [
        f"Replay of source run {report.run_id} -- {report.bundle_root}",
        "  network calls: 0 (offline embedding/generation providers only)",
        f"  original pipeline: adapter={report.original.adapter} "
        f"v{report.original.adapter_version} "
        f"normalization={','.join(report.original.normalization_versions)}",
        f"  current  pipeline: adapter={report.current.adapter} "
        f"v{report.current.adapter_version} "
        f"normalization={','.join(report.current.normalization_versions)}",
        f"  current providers: embedding={report.current.embedding_provider} "
        f"generation={report.current.generation_provider}",
        "  original providers: not recorded (no pre-M4 run captured provider identity)",
    ]
    if report.pipeline_identity_changed:
        lines.append(
            "  pipeline identity differs from the original run: any output "
            "difference below is a replay difference, not historical corruption."
        )
    lines.append(f"  replay would touch {len(report.replay_paths)} file(s):")
    lines.extend(f"    - {path}" for path in report.replay_paths)
    if report.original_commit_sha is not None:
        lines.append(
            f"  original commit: {report.original_commit_sha[:8]} "
            f"touched {len(report.original_paths)} file(s)"
        )
        if report.added_paths or report.removed_paths:
            lines.append(
                "  path differences vs. the original commit (replay difference, not corruption):"
            )
            lines.extend(f"    + {path}" for path in report.added_paths)
            lines.extend(f"    - {path}" for path in report.removed_paths)
        else:
            lines.append("  no path differences vs. the original commit.")
    else:
        lines.append("  no original commit found for this run (not yet merged, or dry-run only).")
    return "\n".join(lines)
