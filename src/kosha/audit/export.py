"""Reconstruct a bundle's compliance evidence from its git commit history.

An ``ingest()`` call's :class:`~kosha.plan.ChangePlan` and
:class:`~kosha.approve.PlanRouting` are pure, in-memory objects — nothing about
them survives past the process that produced them except what lands in the
commit :mod:`kosha.pipeline.run` writes. That commit message is therefore the
durable audit record this module reads back: :func:`kosha.pipeline.run._change_line`
stamps each changed file's lane, impact, confidence, and contradiction state
into the message body, and the existing ``Reviewed-by`` trailer already carries
the approving identity. A ``Source-Run`` trailer plus one sorted
``Evidence-SHA256`` trailer per referenced digest (DEVELOPMENT_PLAN.md M3)
carries evidence lineage the same durable way: no assumption that an
in-memory field survives a reload. Walking every commit reachable from a ref
(default ``HEAD``) reconstructs the whole ingest history without adding any
new on-disk artifact — Git remains the only system of record (system_design
§6).

The export defaults to metadata only: the parsed per-file provenance and
evidence digests, never the file's content or the evidence body itself, and
never the log/source body a bundle carries. Pass ``include_source_text=True``
to additionally attach each changed file's committed content, so a leak of
the export cannot happen by omission. A commit's evidence provenance is
reported honestly: ``"verified"`` only when both trailers are present,
``"legacy"`` for any other ingest commit (pre-M3 history, or a run that
minted no evidence-bound claim) — never fabricated as verified.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from kosha.git_store import GitStore
from kosha.mcp.service import AccessDeniedError
from kosha.okf.errors import OKFError
from kosha.okf.load import load_bundle
from kosha.validate import Report, validate_bundle

_INGEST_SUBJECT = re.compile(r"^feat\(kosha\): ingest (?P<source>.+)$")
_CHANGE_LINE = re.compile(r"^- (?P<kind>create|update) (?P<path>\S+)(?: \[(?P<attrs>[^\]]*)\])?$")
_REVIEWED_BY = re.compile(r"^Reviewed-by: (?P<reviewer>.+)$")
_SOURCE_RUN = re.compile(r"^Source-Run: (?P<run_id>\S+)$")
_EVIDENCE_SHA256 = re.compile(r"^Evidence-SHA256: (?P<digest>[0-9a-f]{64})$")


@dataclass(frozen=True)
class ChangeRecord:
    """One file an ingest commit changed, with the routing provenance it carried.

    ``lane``, ``impact``, ``confidence``, and ``contradiction`` are ``None`` when
    the commit predates the M7 enriched message format (e.g. a bootstrap ``chore:
    seed`` commit) — absence is reported honestly rather than guessed.
    """

    path: str
    kind: str
    lane: str | None
    impact: str | None
    confidence: float | None
    contradiction: str | None
    content: str | None = None


@dataclass(frozen=True)
class CommitRecord:
    """One commit reachable from the export ref.

    ``source_run`` / ``evidence_sha256`` come from the M3 commit trailers;
    both are absent on a commit that predates M3 or minted no evidence-bound
    claim. Use :attr:`evidence_status` rather than testing these directly --
    it is the one place "verified" is decided.
    """

    sha: str
    date: datetime
    subject: str
    source: str | None
    reviewer: str | None
    is_ingest: bool
    changes: tuple[ChangeRecord, ...] = field(default_factory=tuple)
    source_run: str | None = None
    evidence_sha256: tuple[str, ...] = field(default_factory=tuple)

    @property
    def evidence_status(self) -> str:
        """Report this commit's evidence provenance honestly.

        ``"verified"``: an ingest commit carrying both a ``Source-Run``
        trailer and at least one ``Evidence-SHA256`` digest -- the M3
        evidence-backed shape. ``"legacy"``: an ingest commit missing either
        trailer (pre-M3 history, or a run that minted no evidence-bound
        claim) -- never promoted to verified by inference. ``"n/a"``: not an
        ingest commit at all.
        """
        if not self.is_ingest:
            return "n/a"
        if self.source_run is not None and self.evidence_sha256:
            return "verified"
        return "legacy"


@dataclass(frozen=True)
class ComplianceReport:
    """The full compliance-evidence export for a bundle at a point in time."""

    bundle_root: str
    ref: str
    git_remote: str | None
    okf_version: str
    concept_count: int
    commits: tuple[CommitRecord, ...]
    validation: Report

    @property
    def auto_count(self) -> int:
        return sum(1 for c in self.commits for ch in c.changes if ch.lane == "auto")

    @property
    def blocked_count(self) -> int:
        return sum(1 for c in self.commits for ch in c.changes if ch.lane == "block")

    @property
    def contradiction_count(self) -> int:
        return sum(
            1 for c in self.commits for ch in c.changes if ch.contradiction not in (None, "none")
        )

    @property
    def reviewers(self) -> tuple[str, ...]:
        """Every reviewer identity recorded, first-seen order, de-duplicated."""
        seen: list[str] = []
        for commit in self.commits:
            if commit.reviewer is not None and commit.reviewer not in seen:
                seen.append(commit.reviewer)
        return tuple(seen)

    @property
    def verified_evidence_count(self) -> int:
        """Ingest commits whose claims resolve to durable evidence."""
        return sum(1 for c in self.commits if c.evidence_status == "verified")

    @property
    def legacy_provenance_count(self) -> int:
        """Ingest commits with no verifiable evidence trailer."""
        return sum(1 for c in self.commits if c.evidence_status == "legacy")


def require_export_access(bundle_access: str | None, clearance: Iterable[str]) -> None:
    """Raise :class:`~kosha.mcp.service.AccessDeniedError` unless cleared.

    The same bundle-level ACL model the MCP consumer surface enforces
    (system_design §6, §7.2): a compliance export is exactly the kind of
    sensitive artifact the acceptance criterion "ACL restrictions apply to
    lineage and export" means to gate.
    """
    if bundle_access is not None and bundle_access not in frozenset(clearance):
        raise AccessDeniedError(f"bundle access level {bundle_access!r} not in clearance")


def _parse_attrs(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    attrs: dict[str, str] = {}
    for token in raw.split():
        key, _, value = token.partition("=")
        if value:
            attrs[key] = value
    return attrs


def _parse_change_line(line: str) -> ChangeRecord | None:
    match = _CHANGE_LINE.match(line)
    if match is None:
        return None
    attrs = _parse_attrs(match.group("attrs"))
    confidence = float(attrs["confidence"]) if "confidence" in attrs else None
    return ChangeRecord(
        path=match.group("path"),
        kind=match.group("kind"),
        lane=attrs.get("lane"),
        impact=attrs.get("impact"),
        confidence=confidence,
        contradiction=attrs.get("contradiction"),
    )


def _parse_commit_message(
    message: str,
) -> tuple[str, str | None, str | None, tuple[ChangeRecord, ...], str | None, tuple[str, ...]]:
    """Return ``(subject, source, reviewer, changes, source_run, evidence_sha256)``.

    All parsed from a full commit message; ``evidence_sha256`` preserves the
    order the trailers appear in (``commit_plan`` already emits them sorted).
    """
    lines = message.splitlines()
    subject = lines[0] if lines else ""
    subject_match = _INGEST_SUBJECT.match(subject)
    source = subject_match.group("source") if subject_match else None
    changes: list[ChangeRecord] = []
    reviewer: str | None = None
    source_run: str | None = None
    evidence_sha256: list[str] = []
    for line in lines[1:]:
        change = _parse_change_line(line)
        if change is not None:
            changes.append(change)
            continue
        reviewed = _REVIEWED_BY.match(line)
        if reviewed is not None:
            reviewer = reviewed.group("reviewer")
            continue
        run_match = _SOURCE_RUN.match(line)
        if run_match is not None:
            source_run = run_match.group("run_id")
            continue
        digest_match = _EVIDENCE_SHA256.match(line)
        if digest_match is not None:
            evidence_sha256.append(digest_match.group("digest"))
    return subject, source, reviewer, tuple(changes), source_run, tuple(evidence_sha256)


def build_report(
    bundle_root: Path,
    *,
    ref: str = "HEAD",
    include_source_text: bool = False,
) -> ComplianceReport:
    """Reconstruct the compliance evidence for ``bundle_root`` at ``ref``.

    Every commit reachable from ``ref`` is listed, oldest first; a non-ingest
    commit (the initial seed, a manual edit) is still reported, unstructured
    (``is_ingest=False``, ``changes=()``). ``include_source_text=False`` (the
    default) reports only the parsed provenance — never a file's content — so a
    call site must opt in explicitly before source body text can leak through
    an export. Deterministic for a fixed ``bundle_root``/``ref``: two calls
    produce identical output.
    """
    store = GitStore(bundle_root)
    commits: list[CommitRecord] = []
    for sha in store.revisions(ref):
        subject, source, reviewer, changes, source_run, evidence_sha256 = _parse_commit_message(
            store.commit_message(sha)
        )
        if include_source_text:
            changes = tuple(
                replace(change, content=store.show(sha, change.path)) for change in changes
            )
        commits.append(
            CommitRecord(
                sha=sha,
                date=store.commit_date(sha),
                subject=subject,
                source=source,
                reviewer=reviewer,
                is_ingest=source is not None,
                changes=changes,
                source_run=source_run,
                evidence_sha256=evidence_sha256,
            )
        )
    okf_version, concept_count = _bundle_metadata(bundle_root)
    return ComplianceReport(
        bundle_root=str(bundle_root),
        ref=ref,
        git_remote=store.remote_url(),
        okf_version=okf_version,
        concept_count=concept_count,
        commits=tuple(commits),
        validation=validate_bundle(bundle_root),
    )


def _bundle_metadata(bundle_root: Path) -> tuple[str, int]:
    """Return ``(okf_version, concept_count)``, tolerating parse failures.

    A non-conformant bundle must still produce an export — that failure is
    exactly what ``validation`` surfaces, not something this should raise on —
    so an unparseable concept falls back to a raw ``.md`` file count.
    """
    if not bundle_root.is_dir():
        return "0.1", 0
    try:
        bundle = load_bundle(bundle_root)
    except OKFError:
        reserved = {"index.md", "log.md"}
        count = sum(1 for path in bundle_root.rglob("*.md") if path.name not in reserved)
        return "0.1", count
    return bundle.okf_version, len(bundle.concepts)


def _change_json(change: ChangeRecord) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "path": change.path,
        "kind": change.kind,
        "lane": change.lane,
        "impact": change.impact,
        "confidence": change.confidence,
        "contradiction": change.contradiction,
    }
    if change.content is not None:
        payload["content"] = change.content
    return payload


def to_json(report: ComplianceReport) -> dict[str, Any]:
    """Render ``report`` as a JSON-serializable mapping."""
    return {
        "bundle_root": report.bundle_root,
        "ref": report.ref,
        "git_remote": report.git_remote,
        "okf_version": report.okf_version,
        "concept_count": report.concept_count,
        "summary": {
            "commit_count": len(report.commits),
            "ingest_commit_count": sum(1 for c in report.commits if c.is_ingest),
            "auto_count": report.auto_count,
            "blocked_count": report.blocked_count,
            "contradiction_count": report.contradiction_count,
            "reviewers": list(report.reviewers),
            "verified_evidence_count": report.verified_evidence_count,
            "legacy_provenance_count": report.legacy_provenance_count,
        },
        "validation": {
            "ok": report.validation.ok,
            "error_count": len(report.validation.errors),
            "warning_count": len(report.validation.warnings),
            "findings": [
                {
                    "severity": finding.severity.value,
                    "rule": finding.rule.value,
                    "path": finding.path,
                    "message": finding.message,
                }
                for finding in report.validation.findings
            ],
        },
        "commits": [
            {
                "sha": commit.sha,
                "date": commit.date.isoformat(),
                "subject": commit.subject,
                "source": commit.source,
                "reviewer": commit.reviewer,
                "is_ingest": commit.is_ingest,
                "source_run": commit.source_run,
                "evidence_sha256": list(commit.evidence_sha256),
                "evidence_status": commit.evidence_status,
                "changes": [_change_json(change) for change in commit.changes],
            }
            for commit in report.commits
        ],
    }


def to_markdown(report: ComplianceReport) -> str:
    """Render ``report`` as a human-readable Markdown compliance summary.

    A change's ``content`` (set only under ``include_source_text``) renders as
    a fenced code block under its line, matching the JSON renderer's opt-in.
    """
    lines = [
        f"# Compliance export — {report.bundle_root}",
        "",
        f"- ref: `{report.ref}`",
        f"- okf_version: {report.okf_version}",
        f"- concept_count: {report.concept_count}",
        f"- git_remote: {report.git_remote or '(none configured)'}",
        f"- validation: {'OK' if report.validation.ok else 'FAIL'} "
        f"({len(report.validation.errors)} error(s), {len(report.validation.warnings)} warning(s))",
        f"- commits: {len(report.commits)} "
        f"({sum(1 for c in report.commits if c.is_ingest)} ingest)",
        f"- lanes: auto={report.auto_count} blocked={report.blocked_count}",
        f"- contradictions: {report.contradiction_count}",
        f"- reviewers: {', '.join(report.reviewers) or '(none recorded)'}",
        f"- evidence: verified={report.verified_evidence_count} "
        f"legacy={report.legacy_provenance_count}",
        "",
        "## Commits",
        "",
    ]
    for commit in report.commits:
        lines.append(f"### `{commit.sha[:8]}` — {commit.subject}")
        lines.append(f"- date: {commit.date.isoformat()}")
        lines.append(f"- reviewer: {commit.reviewer or '(none recorded)'}")
        if commit.is_ingest:
            lines.append(f"- evidence: {commit.evidence_status}")
        for change in commit.changes:
            detail = f"lane={change.lane or '?'} impact={change.impact or '?'}"
            if change.contradiction and change.contradiction != "none":
                detail += f" contradiction={change.contradiction}"
            lines.append(f"  - {change.kind} {change.path} [{detail}]")
            if change.content is not None:
                lines.append("    ```")
                lines.extend(f"    {line}" for line in change.content.splitlines())
                lines.append("    ```")
        lines.append("")
    if report.validation.findings:
        lines.append("## Validation findings")
        lines.append("")
        for finding in report.validation.findings:
            lines.append(
                f"- {finding.severity.value}: {finding.path}: "
                f"[{finding.rule.value}] {finding.message}"
            )
    return "\n".join(lines).rstrip("\n") + "\n"
