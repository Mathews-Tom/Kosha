"""Verify stored evidence integrity: manifests, objects, and commit-trailer lineage.

:func:`verify_evidence` is the read-only counterpart to
:func:`~kosha.ingest.guardrails.persist_evidence_run`: it walks every source-run
manifest a vault holds, plus every post-M3 ingest commit's ``Source-Run`` /
``Evidence-SHA256`` trailers (:func:`kosha.audit.export.build_report`), and
confirms each one resolves to intact, hash-verified content -- never trusting a
manifest's own bookkeeping. :meth:`~kosha.evidence.store.EvidenceStore.read_run`
only checks object *existence*; a corrupted-but-present object still needs its
bytes re-hashed, which is why every verified run and commit here also calls
:meth:`~kosha.evidence.store.EvidenceStore.read_object` per referenced digest.

A run manifest with no matching commit is still reported (an approved-but-not-
yet-merged or review-queued run); a legacy ingest commit (no evidence trailers)
is counted separately, never silently promoted to "verified"
(DEVELOPMENT_PLAN.md M4; enhancement plan §11).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from kosha.audit.export import CommitRecord, build_report
from kosha.evidence.paths import evidence_root
from kosha.evidence.store import EvidenceCorruptionError, EvidenceStore


@dataclass(frozen=True)
class RunVerification:
    """Verification outcome for one stored source-run manifest."""

    run_id: str
    ok: bool
    evidence_object_count: int = 0
    error: str | None = None


@dataclass(frozen=True)
class CommitVerification:
    """Whether one ingest commit's evidence trailers resolve to intact stored evidence."""

    sha: str
    source_run: str
    evidence_sha256: tuple[str, ...]
    ok: bool
    error: str | None = None


@dataclass(frozen=True)
class VerificationReport:
    """Full evidence-vault integrity report for one bundle at one git ref."""

    bundle_root: str
    evidence_root: str
    ref: str
    runs: tuple[RunVerification, ...] = field(default_factory=tuple)
    commits: tuple[CommitVerification, ...] = field(default_factory=tuple)
    legacy_commit_count: int = 0

    @property
    def ok(self) -> bool:
        """True only when every stored run and every evidence-bearing commit verify clean."""
        return all(run.ok for run in self.runs) and all(commit.ok for commit in self.commits)

    @property
    def corrupt_run_count(self) -> int:
        return sum(1 for run in self.runs if not run.ok)

    @property
    def unresolved_commit_count(self) -> int:
        return sum(1 for commit in self.commits if not commit.ok)


def verify_evidence(
    bundle_root: Path, *, store: EvidenceStore | None = None, ref: str = "HEAD"
) -> VerificationReport:
    """Verify every stored run manifest and every evidence-bearing commit trailer.

    ``store`` overrides vault resolution (tests inject a ``tmp_path``-rooted
    one); the default resolves the operator-private vault at
    ``evidence_root(bundle_root)``. Never raises for expected corruption --
    every failure becomes a non-ok entry in the returned report so a caller
    (the CLI) decides the exit code from :attr:`VerificationReport.ok`.
    """
    vault = store or EvidenceStore(evidence_root(bundle_root))
    runs = tuple(_verify_run(vault, run_id) for run_id in vault.list_run_ids())
    commit_report = build_report(bundle_root, ref=ref)
    commits = tuple(
        _verify_commit(vault, commit)
        for commit in commit_report.commits
        if commit.evidence_status == "verified"
    )
    legacy = sum(1 for commit in commit_report.commits if commit.evidence_status == "legacy")
    return VerificationReport(
        bundle_root=str(bundle_root),
        evidence_root=str(vault.root),
        ref=ref,
        runs=runs,
        commits=commits,
        legacy_commit_count=legacy,
    )


def _verify_run(vault: EvidenceStore, run_id: str) -> RunVerification:
    try:
        run = vault.read_run(run_id)
        for document in run.evidence:
            vault.read_object(document.sha256)  # re-hashes; raises loud on bit rot
    except EvidenceCorruptionError as exc:
        return RunVerification(run_id=run_id, ok=False, error=str(exc))
    return RunVerification(run_id=run_id, ok=True, evidence_object_count=len(run.evidence))


def _verify_commit(vault: EvidenceStore, commit: CommitRecord) -> CommitVerification:
    assert commit.source_run is not None  # evidence_status == "verified" guarantees this
    try:
        run = vault.read_run(commit.source_run)
        manifest_digests = {document.sha256 for document in run.evidence}
        missing = [digest for digest in commit.evidence_sha256 if digest not in manifest_digests]
        if missing:
            raise EvidenceCorruptionError(
                f"commit {commit.sha[:8]} references digest(s) not in run "
                f"{commit.source_run!r}'s manifest: {missing}"
            )
        for digest in commit.evidence_sha256:
            vault.read_object(digest)
    except EvidenceCorruptionError as exc:
        return CommitVerification(
            sha=commit.sha,
            source_run=commit.source_run,
            evidence_sha256=commit.evidence_sha256,
            ok=False,
            error=str(exc),
        )
    return CommitVerification(
        sha=commit.sha,
        source_run=commit.source_run,
        evidence_sha256=commit.evidence_sha256,
        ok=True,
    )


def render_verification_text(report: VerificationReport) -> str:
    """Render ``report`` as a human-readable integrity summary."""
    lines = [
        f"Evidence verification -- {report.bundle_root}",
        f"  vault: {report.evidence_root}",
        f"  ref:   {report.ref}",
        f"  runs:    {len(report.runs)} stored ({report.corrupt_run_count} corrupt)",
        f"  commits: {len(report.commits)} evidence-verified "
        f"({report.unresolved_commit_count} unresolved), "
        f"{report.legacy_commit_count} legacy (pre-M3, no evidence trailer)",
    ]
    corrupt_runs = [run for run in report.runs if not run.ok]
    if corrupt_runs:
        lines.append("")
        lines.append("Corrupt runs:")
        lines.extend(f"  - {run.run_id}: {run.error}" for run in corrupt_runs)
    unresolved = [commit for commit in report.commits if not commit.ok]
    if unresolved:
        lines.append("")
        lines.append("Unresolved commit trailers:")
        lines.extend(
            f"  - {commit.sha[:8]} (run {commit.source_run}): {commit.error}"
            for commit in unresolved
        )
    lines.append("")
    lines.append("OK" if report.ok else "CORRUPTION DETECTED")
    return "\n".join(lines)
