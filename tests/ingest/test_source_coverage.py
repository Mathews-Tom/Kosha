"""Folder-adapter coverage: the default classification `ingest()` derives on its
own, and the explicit override a caller may supply (DEVELOPMENT_PLAN.md M5).

The URL-adapter case lives in `tests/ingest/test_watch.py`, next to the rest of
`ScheduledIngest`'s coverage of the scheduled URL path.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from kosha.evidence import CoverageKind, SourceCoverage
from kosha.git_store import GitStore
from kosha.pipeline import ingest

_ASOF = datetime(2026, 7, 12, tzinfo=UTC)


def _seed_bundle(tmp_path: Path) -> tuple[Path, GitStore]:
    bundle = tmp_path / "bundle"
    (bundle / "policies").mkdir(parents=True)
    (bundle / "policies" / "returns.md").write_text(
        "---\ntype: policy\ntitle: Returns\n"
        "description: When and how customers may return products.\n---\n"
        "Standard returns are accepted within 30 days of delivery.\n",
        encoding="utf-8",
    )
    store = GitStore.init(bundle)
    store.commit(["policies/returns.md"], "chore: seed")
    return bundle, store


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    (source / "policies").mkdir(parents=True)
    (source / "policies" / "returns.md").write_text(
        "# Returns\n\nStandard returns are accepted within 60 days of delivery.\n",
        encoding="utf-8",
    )
    return source


# --- folder adapter: an unstated coverage is derived, never invented as complete


def test_the_folder_adapter_derives_complete_coverage_scoped_to_the_traversal(
    tmp_path: Path,
) -> None:
    bundle, store = _seed_bundle(tmp_path)
    source = _source(tmp_path)
    result = ingest(source, bundle, asof=_ASOF, dry_run=True, git_store=store)

    assert result.evidence_run is not None
    coverage = result.evidence_run.run.coverage
    assert coverage.kind is CoverageKind.COMPLETE
    assert coverage.scope is not None
    assert str(source) in coverage.scope
    assert ".md" in coverage.scope


def test_the_folder_adapters_coverage_reaches_the_affected_file_change(tmp_path: Path) -> None:
    bundle, store = _seed_bundle(tmp_path)
    source = _source(tmp_path)
    result = ingest(source, bundle, asof=_ASOF, dry_run=True, git_store=store)

    updates = [c for c in result.plan.updates if c.evidence_sha256]
    assert updates
    assert updates[0].coverage is not None
    assert updates[0].coverage.kind is CoverageKind.COMPLETE


def test_the_folder_adapters_coverage_lands_in_the_commit_change_line(tmp_path: Path) -> None:
    bundle, store = _seed_bundle(tmp_path)
    source = _source(tmp_path)
    result = ingest(
        source,
        bundle,
        asof=_ASOF,
        source_authority=10,
        git_store=store,
        branch="ingest/coverage-complete",
    )

    assert result.committed is True
    assert "coverage=complete" in store.commit_message()
    assert "coverage_truncated" not in store.commit_message()


# --- an explicit caller-supplied coverage overrides the folder default ----------


def test_an_explicit_coverage_override_replaces_the_folder_default(tmp_path: Path) -> None:
    bundle, store = _seed_bundle(tmp_path)
    source = _source(tmp_path)
    windowed = SourceCoverage(
        kind=CoverageKind.WINDOWED,
        scope="synced changes since the last successful run",
        observed_window_start=datetime(2026, 7, 11, tzinfo=UTC),
        observed_window_end=_ASOF,
    )
    result = ingest(
        source,
        bundle,
        asof=_ASOF,
        dry_run=True,
        git_store=store,
        coverage=windowed,
    )

    assert result.evidence_run is not None
    assert result.evidence_run.run.coverage == windowed


def test_an_explicit_windowed_coverages_kind_lands_in_the_commit_change_line(
    tmp_path: Path,
) -> None:
    bundle, store = _seed_bundle(tmp_path)
    source = _source(tmp_path)
    windowed = SourceCoverage(kind=CoverageKind.WINDOWED, scope="last 24h")
    result = ingest(
        source,
        bundle,
        asof=_ASOF,
        source_authority=10,
        git_store=store,
        branch="ingest/coverage-windowed",
        coverage=windowed,
    )

    assert result.committed is True
    assert "coverage=windowed" in store.commit_message()


# --- a change with no evidence link carries no coverage --------------------------


def test_index_and_log_changes_carry_no_coverage(tmp_path: Path) -> None:
    bundle, store = _seed_bundle(tmp_path)
    source = _source(tmp_path)
    result = ingest(source, bundle, asof=_ASOF, dry_run=True, git_store=store)

    index_and_log = [c for c in result.plan.changes if c.concept_id is None]
    assert index_and_log
    assert all(change.coverage is None for change in index_and_log)
