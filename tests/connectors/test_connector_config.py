"""Explicit connector registry and source-instance config loading (M6/M7)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kosha.connectors.config import (
    CONNECTOR_REGISTRY,
    SourceConfigError,
    UnknownConnectorError,
    load_source_instance,
    load_source_instances,
    resolve_connector,
)


def _write(path: Path, entries: list[dict[str, object]]) -> Path:
    path.write_text(json.dumps(entries), encoding="utf-8")
    return path


# --- explicit registry --------------------------------------------------


def test_the_registry_ships_exactly_folder_url_git_and_mcp() -> None:
    assert set(CONNECTOR_REGISTRY) == {"folder", "url", "git", "mcp"}


def test_resolve_connector_returns_the_matching_definition() -> None:
    definition = resolve_connector("folder")
    assert definition.connector_id == "folder"
    assert definition.required_config_keys == ("path",)


def test_resolve_connector_fails_loud_on_an_unknown_id() -> None:
    with pytest.raises(UnknownConnectorError, match="unknown connector_id 'sharepoint'"):
        resolve_connector("sharepoint")


# --- load_source_instances: fail loud, never fall back -------------------


def test_a_missing_config_file_fails_loud(tmp_path: Path) -> None:
    with pytest.raises(SourceConfigError, match="no source-instance config file"):
        load_source_instances(tmp_path / "nope.json")


def test_malformed_json_fails_loud(tmp_path: Path) -> None:
    path = tmp_path / "sources.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(SourceConfigError, match="malformed source-instance config"):
        load_source_instances(path)


def test_a_non_array_payload_fails_loud(tmp_path: Path) -> None:
    path = tmp_path / "sources.json"
    path.write_text(json.dumps({"instance_id": "x"}), encoding="utf-8")
    with pytest.raises(SourceConfigError, match="must be a JSON array"):
        load_source_instances(path)


def test_an_unknown_connector_id_fails_loud(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "sources.json",
        [{"instance_id": "x", "connector_id": "sharepoint", "config": {}}],
    )
    with pytest.raises(UnknownConnectorError, match="unknown connector_id 'sharepoint'"):
        load_source_instances(path)


def test_a_missing_required_config_key_fails_loud(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "sources.json",
        [{"instance_id": "x", "connector_id": "folder", "config": {}}],
    )
    with pytest.raises(SourceConfigError, match="missing required config key"):
        load_source_instances(path)


def test_a_duplicate_instance_id_fails_loud(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "sources.json",
        [
            {"instance_id": "x", "connector_id": "folder", "config": {"path": "/a"}},
            {"instance_id": "x", "connector_id": "folder", "config": {"path": "/b"}},
        ],
    )
    with pytest.raises(SourceConfigError, match="duplicate instance_id 'x'"):
        load_source_instances(path)


def test_an_invalid_instance_entry_fails_loud(tmp_path: Path) -> None:
    path = _write(tmp_path / "sources.json", [{"instance_id": "x"}])  # missing connector_id
    with pytest.raises(SourceConfigError, match="invalid source instance"):
        load_source_instances(path)


# --- two isolated instances of one connector ------------------------------


def test_two_instances_of_one_connector_load_independently(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "sources.json",
        [
            {"instance_id": "a", "connector_id": "folder", "config": {"path": "/a"}},
            {"instance_id": "b", "connector_id": "folder", "config": {"path": "/b"}},
        ],
    )
    instances = load_source_instances(path)
    assert [i.instance_id for i in instances] == ["a", "b"]
    assert instances[0].config["path"] != instances[1].config["path"]


def test_load_source_instance_returns_the_named_instance(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "sources.json",
        [
            {"instance_id": "a", "connector_id": "folder", "config": {"path": "/a"}},
            {"instance_id": "b", "connector_id": "folder", "config": {"path": "/b"}},
        ],
    )
    instance = load_source_instance(path, "b")
    assert instance.instance_id == "b"
    assert instance.config["path"] == "/b"


def test_load_source_instance_fails_loud_when_not_configured(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "sources.json",
        [{"instance_id": "a", "connector_id": "folder", "config": {"path": "/a"}}],
    )
    with pytest.raises(SourceConfigError, match="no source instance 'missing'"):
        load_source_instance(path, "missing")
