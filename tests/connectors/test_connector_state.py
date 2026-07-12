"""Durable, atomic, per-instance connector state store (M6)."""

from __future__ import annotations

import os
import stat
from datetime import UTC, datetime
from pathlib import Path

import pytest

from kosha.connectors.model import ConnectorState, RunSummary, SourceRunOutcome
from kosha.connectors.state import (
    ConnectorStateCorruptionError,
    ConnectorStateStore,
    connectors_root,
    instance_state_path,
)

_T0 = datetime(2026, 6, 28, tzinfo=UTC)


def _summary(run_id: str = "run-1") -> RunSummary:
    return RunSummary(
        run_id=run_id,
        status=SourceRunOutcome.SUCCESS,
        started_at=_T0,
        completed_at=_T0,
        message="ok",
    )


# --- path resolution: honors KOSHA_HOME, mirrors evidence_root's shape ------


def test_connectors_root_honors_kosha_home_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KOSHA_HOME", "/tmp/example-home")
    assert connectors_root() == Path("/tmp/example-home/connectors")


def test_connectors_root_defaults_under_the_user_home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KOSHA_HOME", raising=False)
    assert connectors_root() == Path.home() / ".kosha" / "connectors"


def test_instance_state_path_rejects_a_path_separator_in_instance_id(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="path separators"):
        instance_state_path(tmp_path, "a/b")


# --- load/save round trip and isolation -------------------------------------


def test_load_returns_none_for_an_instance_that_never_ran(tmp_path: Path) -> None:
    store = ConnectorStateStore(tmp_path)
    assert store.load("never-run") is None


def test_save_then_load_round_trips(tmp_path: Path) -> None:
    store = ConnectorStateStore(tmp_path)
    state = ConnectorState(instance_id="x").advance(_summary(), cursor="cursor-1")
    store.save(state)
    loaded = store.load("x")
    assert loaded is not None
    assert loaded.cursor == "cursor-1"
    assert loaded.last_success_run_id == "run-1"
    assert loaded == state


def test_two_instances_are_stored_and_loaded_independently(tmp_path: Path) -> None:
    store = ConnectorStateStore(tmp_path)
    state_a = ConnectorState(instance_id="a").advance(_summary("run-a"), cursor="cursor-a")
    state_b = ConnectorState(instance_id="b").advance(_summary("run-b"), cursor="cursor-b")
    store.save(state_a)
    store.save(state_b)
    assert store.load("a").cursor == "cursor-a"  # type: ignore[union-attr]
    assert store.load("b").cursor == "cursor-b"  # type: ignore[union-attr]


def test_saving_a_new_state_for_the_same_instance_replaces_the_prior_one(tmp_path: Path) -> None:
    store = ConnectorStateStore(tmp_path)
    first = ConnectorState(instance_id="x").advance(_summary("run-1"), cursor="cursor-1")
    store.save(first)
    second = first.advance(_summary("run-2"), cursor="cursor-2")
    store.save(second)
    loaded = store.load("x")
    assert loaded is not None
    assert loaded.cursor == "cursor-2"
    assert loaded.last_success_run_id == "run-2"


# --- malformed state fails loud, no fallback --------------------------------


def test_malformed_json_on_disk_fails_loud(tmp_path: Path) -> None:
    path = instance_state_path(tmp_path, "x")
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")
    store = ConnectorStateStore(tmp_path)
    with pytest.raises(ConnectorStateCorruptionError, match="malformed connector state"):
        store.load("x")


def test_a_schema_valid_but_semantically_invalid_state_fails_loud(tmp_path: Path) -> None:
    path = instance_state_path(tmp_path, "x")
    path.parent.mkdir(parents=True)
    path.write_text('{"schema_version": 99, "instance_id": "x"}', encoding="utf-8")
    store = ConnectorStateStore(tmp_path)
    with pytest.raises(ConnectorStateCorruptionError, match="invalid connector state"):
        store.load("x")


def test_load_never_falls_back_to_a_fresh_state_on_corruption(tmp_path: Path) -> None:
    # A caller (kosha.connectors.run.run_source_instance) treats a `None`
    # return as "never run" and a fresh cursor. Corruption must never be
    # confused with that -- it always raises instead.
    path = instance_state_path(tmp_path, "x")
    path.parent.mkdir(parents=True)
    path.write_text("null", encoding="utf-8")
    store = ConnectorStateStore(tmp_path)
    with pytest.raises(ConnectorStateCorruptionError):
        store.load("x")


# --- atomic write and permissions -------------------------------------------


def test_save_leaves_no_temp_file_behind(tmp_path: Path) -> None:
    store = ConnectorStateStore(tmp_path)
    store.save(ConnectorState(instance_id="x"))
    instance_dir = tmp_path / "x"
    leftovers = [p for p in instance_dir.iterdir() if p.name != "state.json"]
    assert leftovers == []


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits only")
def test_save_writes_restrictive_permissions(tmp_path: Path) -> None:
    store = ConnectorStateStore(tmp_path)
    path = store.save(ConnectorState(instance_id="x"))
    file_mode = stat.S_IMODE(path.stat().st_mode)
    dir_mode = stat.S_IMODE(path.parent.stat().st_mode)
    assert file_mode == 0o600
    assert dir_mode == 0o700


def test_save_never_partially_overwrites_a_prior_state_on_a_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ConnectorStateStore(tmp_path)
    original = ConnectorState(instance_id="x").advance(_summary("run-1"), cursor="cursor-1")
    store.save(original)

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("kosha.connectors.state.os.replace", _boom)
    with pytest.raises(OSError, match="disk full"):
        store.save(original.advance(_summary("run-2"), cursor="cursor-2"))

    reloaded = store.load("x")
    assert reloaded is not None
    assert reloaded.cursor == "cursor-1"
