"""Connector contracts: SourceInstance, RunSummary, ConnectorState invariants (M6)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from kosha.connectors.model import (
    ConnectorState,
    RunSummary,
    SourceInstance,
    SourceRunOutcome,
)

_T0 = datetime(2026, 6, 28, tzinfo=UTC)


def _summary(status: SourceRunOutcome, *, run_id: str = "run-1", message: str = "") -> RunSummary:
    return RunSummary(
        run_id=run_id, status=status, started_at=_T0, completed_at=_T0, message=message
    )


# --- SourceInstance: identity and non-secret config -------------------------


def test_instance_id_rejects_a_path_separator() -> None:
    with pytest.raises(ValidationError, match="path separators"):
        SourceInstance(instance_id="a/b", connector_id="folder")


def test_instance_id_rejects_empty() -> None:
    with pytest.raises(ValidationError):
        SourceInstance(instance_id="", connector_id="folder")


def test_connector_id_must_not_be_empty() -> None:
    with pytest.raises(ValidationError, match="connector_id must not be empty"):
        SourceInstance(instance_id="x", connector_id="")


def test_a_config_value_matching_a_known_credential_shape_is_rejected() -> None:
    with pytest.raises(ValidationError, match="secret detector"):
        SourceInstance(
            instance_id="x",
            connector_id="folder",
            config={"path": "/tmp", "note": "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE"},
        )


def test_a_config_value_matching_a_generic_credential_assignment_is_rejected() -> None:
    with pytest.raises(ValidationError, match="secret detector"):
        SourceInstance(
            instance_id="x",
            connector_id="folder",
            config={"api_key": "sk-abcdefghijklmnopqrstuvwx"},
        )


def test_an_oversized_config_value_is_rejected_even_without_a_secret_shape() -> None:
    with pytest.raises(ValidationError, match="500 chars"):
        SourceInstance(instance_id="x", connector_id="folder", config={"note": "x" * 501})


def test_config_may_carry_an_env_var_name_not_a_value() -> None:
    # The documented invariant: config stores env-var *names*, never values.
    instance = SourceInstance(
        instance_id="x", connector_id="folder", config={"token_env": "GITHUB_TOKEN"}
    )
    assert instance.config == {"token_env": "GITHUB_TOKEN"}


def test_instance_is_frozen_and_forbids_unknown_fields() -> None:
    instance = SourceInstance(instance_id="x", connector_id="folder")
    with pytest.raises(ValidationError):
        SourceInstance(instance_id="x", connector_id="folder", unexpected="nope")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        instance.enabled = False  # type: ignore[misc]


# --- RunSummary: diagnostics stay short and non-secret -----------------------


def test_a_run_summary_message_matching_a_credential_shape_is_rejected() -> None:
    with pytest.raises(ValidationError, match="secret detector"):
        RunSummary(
            run_id="run-1",
            status=SourceRunOutcome.FAILED,
            started_at=_T0,
            completed_at=_T0,
            message="token: 'sk-abcdefghijklmnopqrstuvwx'",
        )


def test_an_oversized_run_summary_message_is_rejected() -> None:
    with pytest.raises(ValidationError, match="500 chars"):
        RunSummary(
            run_id="run-1",
            status=SourceRunOutcome.FAILED,
            started_at=_T0,
            completed_at=_T0,
            message="x" * 501,
        )


def test_a_run_summary_completed_before_it_started_is_rejected() -> None:
    with pytest.raises(ValidationError, match="completed before it started"):
        RunSummary(
            run_id="run-1",
            status=SourceRunOutcome.SUCCESS,
            started_at=_T0,
            completed_at=_T0 - timedelta(seconds=1),
        )


# --- ConnectorState: cursor only ever moves via advance() -------------------


def test_advance_requires_a_success_summary() -> None:
    state = ConnectorState(instance_id="x")
    with pytest.raises(ValueError, match="requires a SUCCESS"):
        state.advance(_summary(SourceRunOutcome.FAILED), cursor="c1")


def test_record_attempt_rejects_a_success_summary() -> None:
    state = ConnectorState(instance_id="x")
    with pytest.raises(ValueError, match="must not be used for a SUCCESS"):
        state.record_attempt(_summary(SourceRunOutcome.SUCCESS))


def test_advance_sets_cursor_and_last_success_and_appends_history() -> None:
    state = ConnectorState(instance_id="x")
    summary = _summary(SourceRunOutcome.SUCCESS, run_id="run-1")
    advanced = state.advance(summary, cursor="cursor-1")
    assert advanced.cursor == "cursor-1"
    assert advanced.last_success_run_id == "run-1"
    assert advanced.last_success_at == _T0
    assert advanced.recent_runs == (summary,)
    # the original state is untouched -- immutable, functional update
    assert state.cursor is None
    assert state.recent_runs == ()


def test_record_attempt_appends_history_without_touching_cursor() -> None:
    state = ConnectorState(instance_id="x", cursor="cursor-1", last_success_run_id="run-1")
    failed = _summary(SourceRunOutcome.FAILED, run_id="run-2", message="boom")
    updated = state.record_attempt(failed)
    assert updated.cursor == "cursor-1"
    assert updated.last_success_run_id == "run-1"
    assert updated.recent_runs == (failed,)


def test_recent_runs_is_bounded() -> None:
    state = ConnectorState(instance_id="x")
    for i in range(25):
        state = state.record_attempt(_summary(SourceRunOutcome.FAILED, run_id=f"run-{i}"))
    assert len(state.recent_runs) == 20
    assert state.recent_runs[-1].run_id == "run-24"
    assert state.recent_runs[0].run_id == "run-5"


def test_unsupported_schema_version_is_rejected() -> None:
    with pytest.raises(ValidationError, match="schema_version"):
        ConnectorState(instance_id="x", schema_version=99)


def test_state_instance_id_rejects_a_path_separator() -> None:
    with pytest.raises(ValidationError, match="path separators"):
        ConnectorState(instance_id="a/b")
