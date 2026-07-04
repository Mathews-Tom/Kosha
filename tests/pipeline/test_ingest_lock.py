"""Concurrent-ingest lock: exclusive write phase, stale-lock reclaim (M6 PR-3)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from kosha.git_store import GitStore, IngestLock, IngestLockError


def _repo(tmp_path: Path) -> GitStore:
    store = GitStore.init(tmp_path)
    (tmp_path / "README.md").write_text("seed\n", encoding="utf-8")
    store.commit(["README.md"], "chore: seed")
    return store


def test_acquire_creates_a_lock_file_stamped_with_the_holder_pid(tmp_path: Path) -> None:
    store = _repo(tmp_path)
    lock = IngestLock(store.repo)
    lock.acquire()
    try:
        assert lock.path.is_file()
        assert lock.path.read_text(encoding="utf-8").strip() == str(os.getpid())
    finally:
        lock.release()


def test_second_acquire_by_a_live_holder_fails_loud(tmp_path: Path) -> None:
    store = _repo(tmp_path)
    first = IngestLock(store.repo)
    second = IngestLock(store.repo)
    first.acquire()
    try:
        with pytest.raises(IngestLockError, match="another ingest"):
            second.acquire()
    finally:
        first.release()


def test_release_is_safe_when_the_lock_was_never_acquired(tmp_path: Path) -> None:
    store = _repo(tmp_path)
    IngestLock(store.repo).release()  # no-op, must not raise


def test_context_manager_releases_the_lock_on_exit(tmp_path: Path) -> None:
    store = _repo(tmp_path)
    lock = IngestLock(store.repo)
    with lock:
        assert lock.path.is_file()
    assert not lock.path.is_file()


def test_context_manager_releases_the_lock_even_on_exception(tmp_path: Path) -> None:
    store = _repo(tmp_path)
    lock = IngestLock(store.repo)
    with pytest.raises(ValueError, match="boom"), lock:
        raise ValueError("boom")
    assert not lock.path.is_file()


def test_a_stale_lock_from_a_dead_pid_is_reclaimed(tmp_path: Path) -> None:
    store = _repo(tmp_path)
    lock = IngestLock(store.repo)
    lock.path.parent.mkdir(parents=True, exist_ok=True)
    # A PID essentially guaranteed not to be alive in the test sandbox.
    dead_pid = 2**31 - 1
    lock.path.write_text(str(dead_pid), encoding="utf-8")

    lock.acquire()  # must reclaim rather than raise IngestLockError
    try:
        assert lock.path.read_text(encoding="utf-8").strip() == str(os.getpid())
    finally:
        lock.release()


def test_a_lock_held_by_the_current_live_process_is_not_stale(tmp_path: Path) -> None:
    store = _repo(tmp_path)
    first = IngestLock(store.repo)
    first.acquire()
    try:
        with pytest.raises(IngestLockError):
            IngestLock(store.repo).acquire()
    finally:
        first.release()


def test_a_malformed_lock_file_is_left_alone_not_reclaimed(tmp_path: Path) -> None:
    # Defensive: an unparseable lock body (not a bare PID) is never silently
    # treated as stale, since that would defeat the lock's purpose.
    store = _repo(tmp_path)
    lock = IngestLock(store.repo)
    lock.path.parent.mkdir(parents=True, exist_ok=True)
    lock.path.write_text("not-a-pid", encoding="utf-8")

    with pytest.raises(IngestLockError):
        lock.acquire()
