"""A concurrent ingest against a locked bundle fails loudly, not silently (M6 PR-3)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from kosha.git_store import GitStore, IngestLock, IngestLockError
from kosha.pipeline import ingest

_ASOF = datetime(2026, 6, 28, tzinfo=UTC)


def _seed_bundle(tmp_path: Path) -> tuple[Path, GitStore, str]:
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
    return bundle, store, store.current_sha("main")


def _policy_update_source(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    (source / "policies").mkdir(parents=True)
    (source / "policies" / "returns.md").write_text(
        "# Returns\n\nStandard returns are accepted within 60 days of delivery.\n",
        encoding="utf-8",
    )
    return source


def test_second_ingest_fails_loud_while_the_first_holds_the_write_lock(
    tmp_path: Path,
) -> None:
    bundle, store, main_sha = _seed_bundle(tmp_path)
    lock = IngestLock(store.repo)
    lock.acquire()
    try:
        with pytest.raises(IngestLockError):
            ingest(
                _policy_update_source(tmp_path),
                bundle,
                asof=_ASOF,
                source_authority=10,
                git_store=store,
                branch="ingest/racer",
            )
    finally:
        lock.release()

    # The blocked ingest wrote nothing and left main untouched: no partial or
    # interleaved state from the rejected attempt.
    assert store.current_sha("main") == main_sha
    assert not store.branch_exists("ingest/racer")


def test_ingest_releases_the_lock_after_committing_so_a_later_ingest_succeeds(
    tmp_path: Path,
) -> None:
    bundle, store, _ = _seed_bundle(tmp_path)
    lock = IngestLock(store.repo)

    result = ingest(
        _policy_update_source(tmp_path),
        bundle,
        asof=_ASOF,
        source_authority=10,
        git_store=store,
        branch="ingest/first",
    )

    assert result.committed is True
    assert not lock.path.is_file()
