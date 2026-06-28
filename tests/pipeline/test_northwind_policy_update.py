"""Northwind policy-update scenario: the M10 acceptance contract (PR-6).

`kosha ingest` on the policy-update source must UPDATE ``policies/returns.md`` (not
CREATE), mint ``entities/membership-tier.md``, add cross-links, append ``log.md``,
and commit on a branch on approval — while a low-confidence/contradiction run
routes to the block lane and nothing reaches ``main`` without approval
(DEVELOPMENT_PLAN M10; system_design §4.1, §4.5, §6).
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from kosha.approve import Decision
from kosha.git_store import GitStore
from kosha.pipeline import ingest
from kosha.plan import ChangeKind

_FIXTURE = Path(__file__).parent / "fixtures" / "northwind"
_ASOF = datetime(2026, 6, 28, tzinfo=UTC)


def _prepare(tmp_path: Path) -> tuple[Path, GitStore, str]:
    """Copy the seed bundle into a fresh git repo on ``main``; return store + SHA."""
    bundle = tmp_path / "bundle"
    shutil.copytree(_FIXTURE / "bundle", bundle)
    store = GitStore.init(bundle)
    seed = [path.relative_to(bundle).as_posix() for path in sorted(bundle.rglob("*.md"))]
    store.commit(seed, "chore: seed northwind bundle")
    return bundle, store, store.current_sha("main")


def test_northwind_policy_update(tmp_path: Path) -> None:
    bundle, store, main_sha = _prepare(tmp_path)

    result = ingest(
        _FIXTURE / "source",
        bundle,
        asof=_ASOF,
        source_authority=10,
        git_store=store,
        branch="ingest/policy-update",
    )

    changes = {change.path: change for change in result.plan.changes}

    # UPDATE returns (not CREATE) and mint the membership-tier entity.
    assert changes["policies/returns.md"].kind is ChangeKind.UPDATE
    assert changes["entities/membership-tier.md"].kind is ChangeKind.CREATE

    # Cross-links discovered and inserted (bundle-relative standard markdown links).
    returns = (bundle / "policies" / "returns.md").read_text(encoding="utf-8")
    membership = (bundle / "entities" / "membership-tier.md").read_text(encoding="utf-8")
    assert "/entities/membership-tier.md" in returns
    assert "/policies/returns.md" in membership

    # The returns window is superseded to 60 days; the unrelated gold claim survives.
    assert "60 days" in returns
    assert "Gold members receive free return shipping." in returns
    assert "30 days" not in returns

    # The log gained a dated entry per change.
    log = (bundle / "log.md").read_text(encoding="utf-8")
    assert "## 2026-06-28" in log
    assert "Membership Tier" in log

    # Committed on the ingest branch only; main never moved.
    assert result.committed is True
    assert result.decision is Decision.APPROVE
    assert result.branch == "ingest/policy-update"
    assert result.backup_tag == "backup/2026-06-28"
    assert store.head_branch() == "ingest/policy-update"
    assert "entities/membership-tier.md" in store.tracked_files()
    assert store.current_sha("main") == main_sha
    assert "entities/membership-tier.md" not in store.tracked_files("main")


def test_low_confidence_contradiction_routes_to_block(tmp_path: Path) -> None:
    bundle, store, main_sha = _prepare(tmp_path)

    # Equal authority (rank 0) leaves the 30-vs-60-day conflict unresolvable: it
    # escalates, forcing the plan to the block lane.
    result = ingest(
        _FIXTURE / "source",
        bundle,
        asof=_ASOF,
        source_authority=0,
        git_store=store,
        branch="ingest/blocked",
    )

    assert result.routing.requires_approval is True
    assert result.plan.flags  # the escalated contradiction is surfaced for the human
    assert result.decision is Decision.REJECT
    assert result.committed is False
    # Nothing was written or committed: no branch, main untouched.
    assert store.head_branch() == "main"
    assert store.branch_exists("ingest/blocked") is False
    assert store.current_sha("main") == main_sha


def test_blocked_plan_commits_only_with_explicit_approval(tmp_path: Path) -> None:
    bundle, store, main_sha = _prepare(tmp_path)

    result = ingest(
        _FIXTURE / "source",
        bundle,
        asof=_ASOF,
        source_authority=0,
        assume_yes=True,  # explicit human approval of the blocked plan
        git_store=store,
        branch="ingest/approved",
    )

    assert result.routing.requires_approval is True
    assert result.decision is Decision.APPROVE
    assert result.committed is True
    assert store.head_branch() == "ingest/approved"
    assert store.current_sha("main") == main_sha  # still gated off main
