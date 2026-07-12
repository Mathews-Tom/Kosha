"""Bounded Git repository evidence connector (DEVELOPMENT_PLAN.md M7).

Reads deterministic, compact metadata from a configured local repository --
identity, branch/HEAD, a bounded commit-SHA-cursored log with changed-path
name/status only, and (opt-in) working-tree status -- and stages it as
ordinary evidence through the shared connector run boundary
(:mod:`kosha.connectors.run`). It never reads tracked-file content: a
commit's changed paths are reported by name and change kind only, so no
repository secret or ``.env`` file content can ever cross into evidence
(enhancement plan §14).

The commit SHA is the cursor. A cursor that is no longer an ancestor of the
configured branch's HEAD -- a rewritten or force-pushed history -- fails
loud instead of silently re-ingesting or skipping commits; the operator must
resolve it explicitly. Dirty working-tree inclusion is opt-in per instance
and off by default. The configured repository path must resolve inside one
of the operator's ``KOSHA_GIT_ALLOWED_ROOTS`` (a colon-separated list of
absolute directories), the connector's one required environment variable --
so a source-instance config file cannot alone grant read access to an
arbitrary filesystem path.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from kosha.connectors.model import ConnectorRunContext
from kosha.evidence import CoverageKind, SourceCoverage
from kosha.git_store import GitStore
from kosha.ingest.guardrails import build_raw_doc
from kosha.model import Source, SourceKind
from kosha.pipeline import IngestResult, ingest

_ALLOWED_ROOTS_ENV_VAR = "KOSHA_GIT_ALLOWED_ROOTS"
_DEFAULT_MAX_COMMITS = 50
# Git's well-known empty-tree object: diffing a root commit against it yields
# every path the root commit introduced, the same shape `diff_name_status`
# returns for any other commit's parent.
_EMPTY_TREE_SHA = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


class GitConnectorError(ValueError):
    """Raised when a Git source instance's config, path, or cursor is invalid."""


def run_git_source(ctx: ConnectorRunContext) -> IngestResult:
    """Wire the bounded Git connector through ``ingest()``.

    Fails loud (never silently substitutes a fresh cursor or skips the
    check) when the configured path is not a directory, is not a Git
    repository, escapes every allowed root, or the prior cursor is no
    longer an ancestor of the resolved branch's HEAD.
    """
    config = ctx.instance.config
    repo_path = _require_repo_path(config)
    _require_within_allowed_roots(repo_path)
    store = GitStore(repo_path)
    if not store.is_repo():
        raise GitConnectorError(f"not a git repository: {repo_path}")

    ref = config.get("branch") or "HEAD"
    include_dirty = _bool_config(config.get("include_dirty", "false"), field="include_dirty")
    max_commits = _positive_int(
        config.get("max_commits", str(_DEFAULT_MAX_COMMITS)), field="max_commits"
    )
    authority = int(config.get("authority", "0"))

    head_sha = store.current_sha(ref)
    branch_name = config.get("branch") or store.head_branch() or ref
    cursor = ctx.cursor
    if cursor is not None and not store.is_ancestor(cursor, head_sha):
        raise GitConnectorError(
            f"cursor {cursor} is no longer an ancestor of {head_sha} on {branch_name!r}; "
            "the branch was rewritten or force-pushed since the last successful run -- "
            "verify the new history and reset this instance's connector state manually "
            "before running it again"
        )

    commits = store.commit_range(cursor, head_sha, limit=max_commits)
    total = store.count_range(cursor, head_sha)
    text = _render_evidence_text(
        store,
        repo_path=repo_path,
        branch_name=branch_name,
        head_sha=head_sha,
        cursor=cursor,
        commits=commits,
        total=total,
        include_dirty=include_dirty,
    )
    source = Source(
        # `.md`-shaped and instance-stable (not the absolute repo path) so a
        # first-time CREATE draft resolves a valid concept path
        # (`concept_id_from_path`/`new_concept_id`, mirroring the folder
        # adapter's own `source_id == eventual concept path` convention) and
        # stays stable across a repository move -- `location` below carries
        # the actual filesystem path instead.
        source_id=f"git/{ctx.instance.instance_id}.md",
        kind=SourceKind.GIT,
        location=str(repo_path),
        title=f"{repo_path.name} ({branch_name})",
        authority_rank=authority,
        retrieved_at=ctx.asof,
    )
    raw = build_raw_doc(source=source, text=text)
    coverage = SourceCoverage(
        kind=CoverageKind.CURSOR_INCREMENTAL if cursor is not None else CoverageKind.WINDOWED,
        scope=f"bounded commit log for {branch_name!r}, up to {max_commits} commit(s) per run",
        cursor_before=cursor,
        cursor_after=head_sha,
        configured_item_limit=max_commits,
        observed_item_count=len(commits),
        truncated=total > len(commits),
    )
    return ingest(
        repo_path,
        ctx.bundle_root,
        asof=ctx.asof,
        source_authority=authority,
        dry_run=ctx.dry_run,
        assume_yes=ctx.assume_yes,
        reader=ctx.reader,
        reviewer=ctx.reviewer,
        raw_docs=[raw],
        evidence_store=ctx.evidence_store,
        coverage=coverage,
    )


def _render_evidence_text(
    store: GitStore,
    *,
    repo_path: Path,
    branch_name: str,
    head_sha: str,
    cursor: str | None,
    commits: list[str],
    total: int,
    include_dirty: bool,
) -> str:
    """Render deterministic evidence text for a fixed repository state.

    A pure function of the repository's committed history (and, when opted
    in, its working-tree status) -- no wall-clock or run-identity value ever
    enters the text, so re-running against an unchanged repository produces
    byte-identical evidence.
    """
    lines = [f"Git source: {repo_path}", f"Branch: {branch_name}", f"HEAD: {head_sha}"]
    remote = store.remote_url()
    if remote:
        lines.append(f"Remote: {remote}")
    lines.append(f"Commits since {cursor or '(initial)'}: {len(commits)} of {total}")
    lines.append("")
    for sha in commits:
        _, author, when, subject = store.commit_headline(sha)
        parent = store.parent_ref(sha) or _EMPTY_TREE_SHA
        lines.append(f"commit {sha}")
        lines.append(f"Author: {author}")
        lines.append(f"Date: {when.isoformat()}")
        lines.append(f"Subject: {subject}")
        for status, changed_path in store.diff_name_status(parent, sha):
            lines.append(f"  {status} {changed_path}")
        lines.append("")
    if include_dirty:
        dirty = store.status_paths()
        lines.append(f"Working tree status (dirty, opt-in): {len(dirty)} path(s)")
        for status, changed_path in dirty:
            lines.append(f"  {status} {changed_path}")
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def _require_repo_path(config: Mapping[str, str]) -> Path:
    path = Path(config["path"])
    if not path.is_dir():
        raise GitConnectorError(f"not a directory: {path}")
    return path.resolve()


def _require_within_allowed_roots(path: Path, *, env: Mapping[str, str] | None = None) -> None:
    """Fail loud unless ``path`` resolves inside one of ``KOSHA_GIT_ALLOWED_ROOTS``."""
    source = os.environ if env is None else env
    raw = source.get(_ALLOWED_ROOTS_ENV_VAR, "").strip()
    if not raw:
        raise GitConnectorError(
            f"{_ALLOWED_ROOTS_ENV_VAR} is not set; configure at least one operator-approved "
            "root directory before running a git source instance"
        )
    roots = [Path(part).resolve() for part in raw.split(os.pathsep) if part.strip()]
    if any(path == root or root in path.parents for root in roots):
        return
    raise GitConnectorError(
        f"configured path {path} is outside every {_ALLOWED_ROOTS_ENV_VAR} entry"
    )


def _bool_config(raw: str, *, field: str) -> bool:
    normalized = raw.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no", ""}:
        return False
    raise GitConnectorError(f"{field} must be a boolean-shaped value, got {raw!r}")


def _positive_int(raw: str, *, field: str) -> int:
    try:
        value = int(raw)
    except ValueError:
        raise GitConnectorError(f"{field} must be an integer, got {raw!r}") from None
    if value < 1:
        raise GitConnectorError(f"{field} must be positive, got {value}")
    return value
