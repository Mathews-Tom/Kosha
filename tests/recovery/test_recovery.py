"""Backup-tag restore and reindex recovery primitives (M8 PR-4).

Recovery's safety contract: ``describe_*`` shows exact refs/files without
writing anything; ``apply_*`` only mutates on its own branch, only after
verifying the backup ref it depends on (restore) or creating a fresh
``recovery-safety/<timestamp>`` snapshot (both), and always returns an
auditable :class:`RecoveryRecord`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from kosha.git_store import GitStore
from kosha.recovery import (
    RecoveryError,
    RestorePlan,
    append_audit_log,
    apply_reindex,
    apply_restore,
    describe_reindex,
    describe_restore,
    list_backups,
    to_json,
)

_ASOF = datetime(2026, 6, 28, tzinfo=UTC)
_SAFETY_TAG = f"recovery-safety/{_ASOF:%Y%m%d%H%M%S}"

_CONCEPT = """---
type: policy
title: Returns
description: When and how customers may return products.
timestamp: 2026-06-27T10:00:00Z
---

Standard returns are accepted within 30 days of delivery.
"""


def _seeded_repo(tmp_path: Path) -> GitStore:
    """Init a repo with one root-level concept (and no index.md yet)."""
    store = GitStore.init(tmp_path)
    (tmp_path / "returns.md").write_text(_CONCEPT, encoding="utf-8")
    store.commit(["returns.md"], "chore: seed")
    return store


# --- list_backups ------------------------------------------------------------


def test_list_backups_returns_tags_oldest_first(tmp_path: Path) -> None:
    store = _seeded_repo(tmp_path)
    store.tag_daily_backup(datetime(2026, 6, 28, tzinfo=UTC).date())
    store.tag_daily_backup(datetime(2026, 6, 29, tzinfo=UTC).date())
    backups = list_backups(store)
    assert [b.name for b in backups] == ["backup/2026-06-28", "backup/2026-06-29"]
    assert all(b.sha == store.current_sha("HEAD") for b in backups)


def test_list_backups_empty_when_none_exist(tmp_path: Path) -> None:
    store = _seeded_repo(tmp_path)
    assert list_backups(store) == []


# --- restore -----------------------------------------------------------------


def test_describe_restore_shows_the_diff_without_writing(tmp_path: Path) -> None:
    store = _seeded_repo(tmp_path)
    tag = store.tag_daily_backup(_ASOF.date())
    (tmp_path / "returns.md").write_text(_CONCEPT.replace("30 days", "60 days"), encoding="utf-8")
    store.commit(["returns.md"], "feat: extend window")

    plan = describe_restore(store, tag)

    assert plan.tag == tag
    assert [(c.status, c.path) for c in plan.changes] == [("M", "returns.md")]
    # Nothing written: still on main, still the 60-day content.
    assert store.head_branch() == "main"
    assert "60 days" in (tmp_path / "returns.md").read_text(encoding="utf-8")


def test_describe_restore_raises_for_an_unknown_tag(tmp_path: Path) -> None:
    store = _seeded_repo(tmp_path)
    with pytest.raises(RecoveryError, match="backup/2099-01-01"):
        describe_restore(store, "backup/2099-01-01")


def test_apply_restore_verifies_the_backup_ref_immediately_before_mutating(
    tmp_path: Path,
) -> None:
    store = _seeded_repo(tmp_path)
    tag = store.tag_daily_backup(_ASOF.date())
    (tmp_path / "returns.md").write_text(_CONCEPT.replace("30 days", "60 days"), encoding="utf-8")
    store.commit(["returns.md"], "feat: extend window")
    plan = describe_restore(store, tag)
    forged_plan = RestorePlan(
        tag="backup/2099-01-01",  # never created
        ref=plan.ref,
        changes=plan.changes,
    )

    with pytest.raises(RecoveryError, match="backup/2099-01-01"):
        apply_restore(store, forged_plan, asof=_ASOF)

    # Nothing was mutated by the failed attempt.
    assert store.head_branch() == "main"
    assert "60 days" in (tmp_path / "returns.md").read_text(encoding="utf-8")


def test_apply_restore_writes_on_its_own_branch_and_snapshots_a_safety_tag(
    tmp_path: Path,
) -> None:
    store = _seeded_repo(tmp_path)
    tag = store.tag_daily_backup(_ASOF.date())
    (tmp_path / "returns.md").write_text(_CONCEPT.replace("30 days", "60 days"), encoding="utf-8")
    main_sha = store.commit(["returns.md"], "feat: extend window")
    plan = describe_restore(store, tag)

    record = apply_restore(store, plan, asof=_ASOF)

    assert record.applied is True
    assert record.action == "restore"
    assert record.source_ref == tag
    assert record.branch is not None and record.branch != "main"
    assert store.head_branch() == record.branch
    assert store.current_sha("main") == main_sha  # main never moved
    assert store.tag_exists(tag)  # the original backup ref is untouched
    assert store.current_sha(tag) != store.current_sha("main")
    assert record.backup_tag == _SAFETY_TAG  # a distinct, freshly-taken safety snapshot
    assert store.tag_exists(_SAFETY_TAG)
    assert store.current_sha(_SAFETY_TAG) == main_sha
    assert "30 days" in (tmp_path / "returns.md").read_text(encoding="utf-8")
    assert record.commit_sha == store.current_sha("HEAD")


def test_apply_restore_with_no_differences_writes_nothing(tmp_path: Path) -> None:
    store = _seeded_repo(tmp_path)
    tag = store.tag_daily_backup(_ASOF.date())
    plan = describe_restore(store, tag)
    assert plan.is_empty

    record = apply_restore(store, plan, asof=_ASOF)

    assert record.applied is False
    assert record.commit_sha is None
    assert store.head_branch() == "main"
    assert store.tags_matching("recovery-safety/") == []  # no mutation, no safety tag taken


# --- reindex -------------------------------------------------------------


def test_describe_reindex_detects_a_missing_index(tmp_path: Path) -> None:
    store = _seeded_repo(tmp_path)
    assert not (tmp_path / "index.md").is_file()

    plan = describe_reindex(tmp_path)

    assert [(c.action, c.path) for c in plan.changes] == [("create", "index.md")]
    assert not (tmp_path / "index.md").is_file()  # describe never writes
    assert store.head_branch() == "main"


def test_describe_reindex_detects_a_stale_index(tmp_path: Path) -> None:
    store = _seeded_repo(tmp_path)
    (tmp_path / "index.md").write_text(
        "---\nokf_version: '0.1'\n---\n\n# stale, wrong content\n", encoding="utf-8"
    )
    store.commit(["index.md"], "chore: stale index")

    plan = describe_reindex(tmp_path)

    assert [(c.action, c.path) for c in plan.changes] == [("update", "index.md")]


def test_apply_reindex_writes_only_the_drifted_files_and_snapshots_a_backup(
    tmp_path: Path,
) -> None:
    store = _seeded_repo(tmp_path)
    plan = describe_reindex(tmp_path)

    record = apply_reindex(store, tmp_path, plan, asof=_ASOF)

    assert record.applied is True
    assert record.action == "reindex"
    assert record.paths == ("index.md",)
    assert store.head_branch() == record.branch
    assert (tmp_path / "index.md").is_file()
    assert record.backup_tag == _SAFETY_TAG
    assert store.tag_exists(_SAFETY_TAG)


def test_describe_reindex_empty_once_applied(tmp_path: Path) -> None:
    store = _seeded_repo(tmp_path)
    plan = describe_reindex(tmp_path)
    record = apply_reindex(store, tmp_path, plan, asof=_ASOF)
    assert record.applied is True
    store.switch("main")  # apply_reindex commits on its own branch, not main

    # main never received the reindex commit, so describe still sees drift there.
    assert not describe_reindex(tmp_path).is_empty
    store.switch(record.branch)  # type: ignore[arg-type]
    assert describe_reindex(tmp_path).is_empty


def test_apply_reindex_with_no_drift_writes_nothing(tmp_path: Path) -> None:
    store = _seeded_repo(tmp_path)
    plan = describe_reindex(tmp_path)
    record = apply_reindex(store, tmp_path, plan, asof=_ASOF)
    store.switch(record.branch)  # type: ignore[arg-type]

    up_to_date_plan = describe_reindex(tmp_path)
    assert up_to_date_plan.is_empty

    second_record = apply_reindex(store, tmp_path, up_to_date_plan, asof=_ASOF)

    assert second_record.applied is False
    assert second_record.commit_sha is None


# --- audit trail ---------------------------------------------------------


def test_to_json_renders_paths_as_a_list(tmp_path: Path) -> None:
    store = _seeded_repo(tmp_path)
    plan = describe_reindex(tmp_path)
    record = apply_reindex(store, tmp_path, plan, asof=_ASOF)

    payload = to_json(record)

    assert payload["action"] == "reindex"
    assert payload["applied"] is True
    assert payload["paths"] == ["index.md"]
    assert payload["backup_tag"] == _SAFETY_TAG


def test_append_audit_log_writes_one_json_line_per_call(tmp_path: Path) -> None:
    store = _seeded_repo(tmp_path)
    plan = describe_reindex(tmp_path)
    record = apply_reindex(store, tmp_path, plan, asof=_ASOF)
    log_path = tmp_path.parent / "audit" / "recovery.jsonl"

    append_audit_log(log_path, record)
    append_audit_log(log_path, record)

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == to_json(record)
