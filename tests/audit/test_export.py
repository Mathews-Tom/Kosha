"""Compliance-grade audit export over a bundle's git history (M7 PR-3)."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from kosha.audit import build_report, require_export_access, to_json, to_markdown
from kosha.git_store import GitStore
from kosha.mcp.service import AccessDeniedError
from kosha.pipeline import ingest

_ASOF = datetime(2026, 6, 28, tzinfo=UTC)


def _seed_bundle(tmp_path: Path) -> tuple[Path, GitStore]:
    bundle = tmp_path / "bundle"
    (bundle / "policies").mkdir(parents=True)
    (bundle / "policies" / "returns.md").write_text(
        "---\ntype: policy\ntitle: Returns\n"
        "description: When and how customers may return products.\n---\n"
        "Standard returns are accepted within 30 days of delivery.\n\n"
        "Gold members receive free return shipping.\n",
        encoding="utf-8",
    )
    store = GitStore.init(bundle)
    store.commit(["policies/returns.md"], "chore: seed")
    return bundle, store


def _policy_update_source(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    (source / "policies").mkdir(parents=True)
    (source / "policies" / "returns.md").write_text(
        "# Returns\n\nStandard returns are accepted within 60 days of delivery.\n",
        encoding="utf-8",
    )
    return source


def _ingest_once(tmp_path: Path, bundle: Path, store: GitStore, *, reviewer: str | None) -> None:
    result = ingest(
        _policy_update_source(tmp_path),
        bundle,
        asof=_ASOF,
        source_authority=10,
        git_store=store,
        branch="ingest/test",
        reviewer=reviewer,
    )
    assert result.committed is True


def test_build_report_lists_the_seed_commit_unstructured(tmp_path: Path) -> None:
    bundle, _ = _seed_bundle(tmp_path)
    report = build_report(bundle)
    assert len(report.commits) == 1
    seed = report.commits[0]
    assert seed.is_ingest is False
    assert seed.changes == ()
    assert seed.reviewer is None


def test_build_report_reconstructs_ingest_decisions_lanes_and_contradictions(
    tmp_path: Path,
) -> None:
    bundle, store = _seed_bundle(tmp_path)
    _ingest_once(tmp_path, bundle, store, reviewer="Jane Doe <jane@example.com>")

    report = build_report(bundle)
    assert len(report.commits) == 2
    ingest_commit = report.commits[-1]
    assert ingest_commit.is_ingest is True
    assert ingest_commit.source == "source"
    assert ingest_commit.reviewer == "Jane Doe <jane@example.com>"
    assert ingest_commit.sha == store.current_sha("HEAD")

    paths = {change.path for change in ingest_commit.changes}
    assert "policies/returns.md" in paths
    update = next(c for c in ingest_commit.changes if c.path == "policies/returns.md")
    assert update.kind == "update"
    assert update.lane in ("auto", "skim", "block")
    assert update.contradiction == "resolved"
    assert update.confidence is not None

    assert report.reviewers == ("Jane Doe <jane@example.com>",)
    assert report.contradiction_count == 1
    assert report.blocked_count == 0


def test_build_report_omits_reviewer_when_none_supplied(tmp_path: Path) -> None:
    bundle, store = _seed_bundle(tmp_path)
    _ingest_once(tmp_path, bundle, store, reviewer=None)
    report = build_report(bundle)
    assert report.commits[-1].reviewer is None
    assert report.reviewers == ()


def test_build_report_includes_current_validation_outcome(tmp_path: Path) -> None:
    bundle, _ = _seed_bundle(tmp_path)
    report = build_report(bundle)
    assert report.validation.ok is True
    assert report.validation.errors == []


def test_build_report_surfaces_validation_failures(tmp_path: Path) -> None:
    bundle, store = _seed_bundle(tmp_path)
    (bundle / "policies" / "broken.md").write_text("no frontmatter here\n", encoding="utf-8")
    store.commit(["policies/broken.md"], "chore: add a non-conformant file")
    report = build_report(bundle)
    assert report.validation.ok is False
    assert report.validation.errors


def test_build_report_is_deterministic_for_a_fixed_ref(tmp_path: Path) -> None:
    bundle, store = _seed_bundle(tmp_path)
    _ingest_once(tmp_path, bundle, store, reviewer="Jane Doe <jane@example.com>")
    first = to_json(build_report(bundle))
    second = to_json(build_report(bundle))
    assert first == second


def test_to_json_excludes_source_text_by_default(tmp_path: Path) -> None:
    bundle, store = _seed_bundle(tmp_path)
    _ingest_once(tmp_path, bundle, store, reviewer=None)
    payload = to_json(build_report(bundle))
    for commit in payload["commits"]:
        for change in commit["changes"]:
            assert "content" not in change


def test_to_json_includes_source_text_only_when_requested(tmp_path: Path) -> None:
    bundle, store = _seed_bundle(tmp_path)
    _ingest_once(tmp_path, bundle, store, reviewer=None)
    payload = to_json(build_report(bundle, include_source_text=True))
    ingest_commit = next(c for c in payload["commits"] if c["is_ingest"])
    update = next(c for c in ingest_commit["changes"] if c["path"] == "policies/returns.md")
    assert "60 days" in update["content"]


def test_to_markdown_reports_summary_and_per_commit_detail(tmp_path: Path) -> None:
    bundle, store = _seed_bundle(tmp_path)
    _ingest_once(tmp_path, bundle, store, reviewer="Jane Doe <jane@example.com>")
    document = to_markdown(build_report(bundle))
    assert "# Compliance export" in document
    assert "reviewers: Jane Doe <jane@example.com>" in document
    assert "feat(kosha): ingest source" in document
    assert "update policies/returns.md" in document


def test_to_markdown_includes_source_text_only_when_requested(tmp_path: Path) -> None:
    bundle, store = _seed_bundle(tmp_path)
    _ingest_once(tmp_path, bundle, store, reviewer=None)
    without_text = to_markdown(build_report(bundle))
    assert "60 days" not in without_text
    with_text = to_markdown(build_report(bundle, include_source_text=True))
    assert "60 days" in with_text
    assert "```" in with_text


def test_build_report_surfaces_the_configured_remote(tmp_path: Path) -> None:
    bundle, _ = _seed_bundle(tmp_path)
    subprocess.run(
        ["git", "-C", str(bundle), "remote", "add", "origin", "https://example.com/repo.git"],
        check=True,
        capture_output=True,
    )
    report = build_report(bundle)
    assert report.git_remote == "https://example.com/repo.git"


def test_build_report_reports_no_remote_when_unconfigured(tmp_path: Path) -> None:
    bundle, _ = _seed_bundle(tmp_path)
    report = build_report(bundle)
    assert report.git_remote is None


def test_build_report_parses_a_pre_m7_commit_without_bracketed_attrs(tmp_path: Path) -> None:
    bundle, store = _seed_bundle(tmp_path)
    (bundle / "policies" / "shipping.md").write_text(
        "---\ntype: policy\ntitle: Shipping\n---\nShips within 3 days.\n", encoding="utf-8"
    )
    store.commit(
        ["policies/shipping.md"],
        "feat(kosha): ingest legacy\n\n- create policies/shipping.md",
    )
    report = build_report(bundle)
    legacy = report.commits[-1]
    assert legacy.is_ingest is True
    assert legacy.source == "legacy"
    change = legacy.changes[0]
    assert change.path == "policies/shipping.md"
    assert change.kind == "create"
    assert change.lane is None
    assert change.impact is None
    assert change.confidence is None
    assert change.contradiction is None


def test_require_export_access_denies_an_uncleared_bundle() -> None:
    with pytest.raises(AccessDeniedError):
        require_export_access("confidential", [])


def test_require_export_access_allows_a_cleared_bundle() -> None:
    require_export_access("confidential", ["confidential"])  # does not raise


def test_require_export_access_allows_an_open_bundle() -> None:
    require_export_access(None, [])  # does not raise
