"""Allowlisted, read-only MCP source connector (DEVELOPMENT_PLAN.md M7)."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from kosha.connectors.config import MCP_CONNECTOR
from kosha.connectors.mcp import (
    McpAuthorizationError,
    McpConnectorError,
    hash_arguments,
    hash_tool_schema,
    run_mcp_source,
)
from kosha.connectors.model import ConnectorRunContext, SourceInstance, SourceRunOutcome
from kosha.connectors.run import run_source_instance
from kosha.connectors.state import ConnectorStateStore
from kosha.evidence import EvidenceStore, evidence_root
from kosha.git_store import GitStore

_ASOF = datetime(2026, 6, 28, tzinfo=UTC)
_FIXTURE_SERVER = Path(__file__).parent / "fixtures" / "fake_mcp_server.py"


def _seed_bundle(tmp_path: Path) -> Path:
    bundle = tmp_path / "bundle"
    (bundle / "policies").mkdir(parents=True)
    (bundle / "policies" / "returns.md").write_text(
        "---\ntype: policy\ntitle: Returns\n"
        "description: When and how customers may return products.\n---\n"
        "Standard returns are accepted within 30 days of delivery.\n",
        encoding="utf-8",
    )
    GitStore.init(bundle).commit(["policies/returns.md"], "chore: seed")
    return bundle


def _instance(
    instance_id: str, tool_name: str, allowed_tools: str, **config: str
) -> SourceInstance:
    return SourceInstance(
        instance_id=instance_id,
        connector_id="mcp",
        config={
            "command": sys.executable,
            "args": str(_FIXTURE_SERVER),
            "tool_name": tool_name,
            "allowed_tools": allowed_tools,
            **config,
        },
    )


def _dry_run_ctx(instance: SourceInstance, bundle: Path) -> ConnectorRunContext:
    return ConnectorRunContext(
        instance=instance,
        bundle_root=bundle,
        asof=_ASOF,
        cursor=None,
        evidence_store=EvidenceStore(evidence_root(bundle)),
        dry_run=True,
        assume_yes=True,
        reviewer=None,
        reader=None,
    )


def _live_schema_hash(tool_name: str) -> str:
    """Fetch the fixture server's live schema hash for ``tool_name`` (real, local subprocess)."""
    import anyio
    from mcp.client.stdio import StdioServerParameters, stdio_client

    from mcp import ClientSession

    async def _fetch() -> str:
        params = StdioServerParameters(command=sys.executable, args=[str(_FIXTURE_SERVER)])
        async with (
            stdio_client(params) as (read_stream, write_stream),
            ClientSession(read_stream, write_stream) as session,
        ):
            await session.initialize()
            listing = await session.list_tools()
            tool = next(t for t in listing.tools if t.name == tool_name)
            return hash_tool_schema(tool.inputSchema)

    return anyio.run(_fetch)


# --- registry shape ------------------------------------------------------------


def test_the_mcp_connector_is_registered_with_no_cursor_support() -> None:
    assert MCP_CONNECTOR.connector_id == "mcp"
    assert MCP_CONNECTOR.required_config_keys == ("command", "tool_name")
    assert MCP_CONNECTOR.supports_cursor is False


# --- allowed read-only call succeeds ---------------------------------------------


def test_an_allowlisted_read_only_tool_succeeds(tmp_path: Path) -> None:
    bundle = _seed_bundle(tmp_path)
    instance = _instance("src", "list_items", "list_items")
    result = run_mcp_source(_dry_run_ctx(instance, bundle))
    assert result.evidence_run is not None
    text = next(iter(result.evidence_run.texts.values()))
    assert "item-1" in text
    assert "Tool: list_items" in text
    assert "Schema SHA-256:" in text
    assert "Argument SHA-256:" in text


# --- unlisted tool is rejected, before any transport call ------------------------


def test_an_unlisted_tool_is_rejected_without_connecting(tmp_path: Path) -> None:
    bundle = _seed_bundle(tmp_path)
    instance = _instance("src", "list_items", allowed_tools="")
    with pytest.raises(McpAuthorizationError, match="not in this instance's allowlist"):
        run_mcp_source(_dry_run_ctx(instance, bundle))


def test_a_tool_name_the_live_server_does_not_advertise_is_rejected(tmp_path: Path) -> None:
    bundle = _seed_bundle(tmp_path)
    instance = _instance("src", "does_not_exist", "does_not_exist")
    with pytest.raises(McpAuthorizationError, match="does not currently advertise"):
        run_mcp_source(_dry_run_ctx(instance, bundle))


# --- destructive tool always rejected --------------------------------------------


def test_a_destructive_tool_is_rejected_even_when_allowlisted_and_pinned(tmp_path: Path) -> None:
    bundle = _seed_bundle(tmp_path)
    instance = _instance(
        "src",
        "delete_everything",
        "delete_everything",
        pinned_schema_hashes=json.dumps({"delete_everything": "0" * 64}),
    )
    with pytest.raises(McpAuthorizationError, match="destructiveHint=true"):
        run_mcp_source(_dry_run_ctx(instance, bundle))


# --- neither read-only nor pinned is rejected; a correct pin succeeds ------------


def test_an_unannotated_tool_without_a_pin_is_rejected(tmp_path: Path) -> None:
    bundle = _seed_bundle(tmp_path)
    instance = _instance("src", "unannotated_read", "unannotated_read")
    with pytest.raises(McpAuthorizationError, match="no operator-pinned schema hash"):
        run_mcp_source(_dry_run_ctx(instance, bundle))


def test_an_unannotated_tool_with_a_correct_pin_succeeds(tmp_path: Path) -> None:
    bundle = _seed_bundle(tmp_path)
    correct_hash = _live_schema_hash("unannotated_read")
    instance = _instance(
        "src",
        "unannotated_read",
        "unannotated_read",
        pinned_schema_hashes=json.dumps({"unannotated_read": correct_hash}),
    )
    result = run_mcp_source(_dry_run_ctx(instance, bundle))
    assert result.evidence_run is not None
    text = next(iter(result.evidence_run.texts.values()))
    assert "unannotated payload" in text
    assert f"Schema SHA-256: {correct_hash}" in text


def test_an_unannotated_tool_with_a_wrong_pin_is_rejected_as_drift(tmp_path: Path) -> None:
    bundle = _seed_bundle(tmp_path)
    instance = _instance(
        "src",
        "unannotated_read",
        "unannotated_read",
        pinned_schema_hashes=json.dumps({"unannotated_read": "f" * 64}),
    )
    with pytest.raises(McpAuthorizationError, match="schema has drifted"):
        run_mcp_source(_dry_run_ctx(instance, bundle))


# --- argument/schema hashes are recorded ------------------------------------------


def test_argument_hash_reflects_the_configured_arguments(tmp_path: Path) -> None:
    bundle = _seed_bundle(tmp_path)
    instance = _instance(
        "src", "echo_args", "echo_args", arguments=json.dumps({"value": "hello"})
    )
    result = run_mcp_source(_dry_run_ctx(instance, bundle))
    assert result.evidence_run is not None
    text = next(iter(result.evidence_run.texts.values()))
    assert "echo:hello" in text
    expected_hash = hash_arguments({"value": "hello"})
    assert f"Argument SHA-256: {expected_hash}" in text


# --- oversized response fails before persistence ----------------------------------


def test_an_oversized_response_fails_loud_and_preserves_state(tmp_path: Path) -> None:
    bundle = _seed_bundle(tmp_path)
    state_store = ConnectorStateStore(tmp_path / "state")
    instance = _instance("src", "big_tool", "big_tool", max_output_bytes="100")
    report = run_source_instance(
        instance, bundle_root=bundle, state_store=state_store, asof=_ASOF, assume_yes=True
    )
    assert report.outcome is SourceRunOutcome.FAILED
    assert "max_output_bytes=100" in report.message
    assert report.state.last_success_run_id is None


# --- timeout fails loud -----------------------------------------------------------


def test_a_slow_tool_times_out_and_preserves_state(tmp_path: Path) -> None:
    bundle = _seed_bundle(tmp_path)
    state_store = ConnectorStateStore(tmp_path / "state")
    instance = _instance("src", "slow_tool", "slow_tool", timeout_seconds="1")
    report = run_source_instance(
        instance, bundle_root=bundle, state_store=state_store, asof=_ASOF, assume_yes=True
    )
    assert report.outcome is SourceRunOutcome.FAILED
    assert report.state.last_success_run_id is None


# --- transport failure never advances state ---------------------------------------


def test_a_missing_server_command_fails_loud_and_preserves_state(tmp_path: Path) -> None:
    bundle = _seed_bundle(tmp_path)
    state_store = ConnectorStateStore(tmp_path / "state")
    instance = SourceInstance(
        instance_id="src",
        connector_id="mcp",
        config={
            "command": "definitely-not-a-real-mcp-server-binary",
            "tool_name": "list_items",
            "allowed_tools": "list_items",
        },
    )
    report = run_source_instance(
        instance, bundle_root=bundle, state_store=state_store, asof=_ASOF, assume_yes=True
    )
    assert report.outcome is SourceRunOutcome.FAILED
    assert report.state.last_success_run_id is None


# --- credentials/headers stay out of config, state, and run messages --------------


def test_forwarded_env_vars_pass_only_the_named_variable_into_the_subprocess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _seed_bundle(tmp_path)
    monkeypatch.setenv("KOSHA_TEST_PROBE", "forwarded-secret-value")
    instance = _instance(
        "src",
        "env_probe",
        "env_probe",
        arguments=json.dumps({"var_name": "KOSHA_TEST_PROBE"}),
        forwarded_env_vars="KOSHA_TEST_PROBE",
    )
    result = run_mcp_source(_dry_run_ctx(instance, bundle))
    assert result.evidence_run is not None
    text = next(iter(result.evidence_run.texts.values()))
    assert "value=forwarded-secret-value" in text
    # Kosha's own config never stores the resolved value -- only the name.
    assert "forwarded-secret-value" not in json.dumps(instance.model_dump(mode="json"))


def test_an_env_var_not_declared_as_forwarded_is_not_visible_to_the_subprocess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _seed_bundle(tmp_path)
    monkeypatch.setenv("KOSHA_TEST_PROBE", "forwarded-secret-value")
    instance = _instance(
        "src", "env_probe", "env_probe", arguments=json.dumps({"var_name": "KOSHA_TEST_PROBE"})
    )
    result = run_mcp_source(_dry_run_ctx(instance, bundle))
    assert result.evidence_run is not None
    text = next(iter(result.evidence_run.texts.values()))
    assert "value=<unset>" in text


def test_a_declared_but_unset_forwarded_env_var_fails_loud(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _seed_bundle(tmp_path)
    monkeypatch.delenv("KOSHA_MISSING_PROBE", raising=False)
    instance = _instance(
        "src", "list_items", "list_items", forwarded_env_vars="KOSHA_MISSING_PROBE"
    )
    with pytest.raises(McpConnectorError, match="forwarded_env_vars names"):
        run_mcp_source(_dry_run_ctx(instance, bundle))


def test_credentials_never_appear_in_the_run_report_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _seed_bundle(tmp_path)
    monkeypatch.setenv("KOSHA_TEST_PROBE", "forwarded-secret-value")
    state_store = ConnectorStateStore(tmp_path / "state")
    instance = _instance(
        "src",
        "env_probe",
        "env_probe",
        arguments=json.dumps({"var_name": "KOSHA_TEST_PROBE"}),
        forwarded_env_vars="KOSHA_TEST_PROBE",
    )
    report = run_source_instance(
        instance, bundle_root=bundle, state_store=state_store, asof=_ASOF, assume_yes=True
    )
    assert "forwarded-secret-value" not in report.message
    assert "forwarded-secret-value" not in json.dumps(report.state.model_dump(mode="json"))
