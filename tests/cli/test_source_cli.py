"""``kosha source list|run|status`` at the CLI layer (M6).

Every scenario relies on the autouse ``KOSHA_HOME`` redirect in
``tests/conftest.py``: connector state and the CLI both resolve the same
default, per-test-isolated ``~/.kosha/connectors/`` root, so no test needs to
inject an explicit ``ConnectorStateStore``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kosha.cli import main
from kosha.connectors.state import ConnectorStateStore, connectors_root
from kosha.git_store import GitStore


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


def _seed_source(tmp_path: Path, *, name: str = "source", body: str = "shipping.md") -> Path:
    source = tmp_path / name
    source.mkdir()
    (source / body).write_text(
        "---\ntype: policy\ntitle: Shipping\ndescription: How shipping works.\n---\n"
        "Orders ship within 2 business days.\n",
        encoding="utf-8",
    )
    return source


def _write_config(path: Path, entries: list[dict[str, object]]) -> Path:
    path.write_text(json.dumps(entries), encoding="utf-8")
    return path


# --- kosha source (no subcommand) -------------------------------------


def test_source_with_no_subcommand_prints_usage_and_exits_2(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(["source"])
    assert code == 2
    assert "list, run, status" in capsys.readouterr().err


# --- kosha source list ---------------------------------------------------


def test_source_list_rejects_a_missing_config_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["source", "list", "--config", str(tmp_path / "nope.json")])
    assert code == 2
    assert "no source-instance config file" in capsys.readouterr().err


def test_source_list_rejects_an_unknown_connector_id(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = _write_config(
        tmp_path / "sources.json",
        [{"instance_id": "x", "connector_id": "sharepoint", "config": {}}],
    )
    code = main(["source", "list", "--config", str(config)])
    assert code == 2
    assert "unknown connector_id 'sharepoint'" in capsys.readouterr().err


def test_source_list_prints_every_configured_instance(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = _seed_source(tmp_path)
    config = _write_config(
        tmp_path / "sources.json",
        [
            {"instance_id": "a", "connector_id": "folder", "config": {"path": str(source)}},
            {
                "instance_id": "b",
                "connector_id": "folder",
                "config": {"path": str(source)},
                "enabled": False,
            },
        ],
    )
    code = main(["source", "list", "--config", str(config)])
    assert code == 0
    out = capsys.readouterr().out
    assert "a\tfolder\tenabled" in out
    assert "b\tfolder\tdisabled" in out


def test_source_list_json_reports_every_instance(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = _seed_source(tmp_path)
    config = _write_config(
        tmp_path / "sources.json",
        [{"instance_id": "a", "connector_id": "folder", "config": {"path": str(source)}}],
    )
    code = main(["source", "list", "--config", str(config), "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["instances"] == [
        {"instance_id": "a", "connector_id": "folder", "enabled": True, "schedule": None}
    ]


# --- kosha source run ------------------------------------------------------


def test_source_run_rejects_an_unconfigured_instance(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = _seed_bundle(tmp_path)
    source = _seed_source(tmp_path)
    config = _write_config(
        tmp_path / "sources.json",
        [{"instance_id": "a", "connector_id": "folder", "config": {"path": str(source)}}],
    )
    code = main(
        ["source", "run", "missing", "--config", str(config), "--bundle", str(bundle), "--yes"]
    )
    assert code == 2
    assert "no source instance 'missing'" in capsys.readouterr().err


def test_source_run_rejects_a_missing_bundle_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = _seed_source(tmp_path)
    config = _write_config(
        tmp_path / "sources.json",
        [{"instance_id": "a", "connector_id": "folder", "config": {"path": str(source)}}],
    )
    code = main(
        [
            "source",
            "run",
            "a",
            "--config",
            str(config),
            "--bundle",
            str(tmp_path / "nope"),
            "--yes",
        ]
    )
    assert code == 2
    assert "not a bundle directory" in capsys.readouterr().err


def test_source_run_commits_and_advances_state_on_success(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = _seed_bundle(tmp_path)
    source = _seed_source(tmp_path)
    config = _write_config(
        tmp_path / "sources.json",
        [{"instance_id": "policies", "connector_id": "folder", "config": {"path": str(source)}}],
    )
    code = main(
        ["source", "run", "policies", "--config", str(config), "--bundle", str(bundle), "--yes"]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "policies: success:" in out
    assert "committed" in out

    state = ConnectorStateStore(connectors_root()).load("policies")
    assert state is not None
    assert state.last_success_run_id is not None


def test_source_run_json_reports_the_committed_result(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = _seed_bundle(tmp_path)
    source = _seed_source(tmp_path)
    config = _write_config(
        tmp_path / "sources.json",
        [{"instance_id": "policies", "connector_id": "folder", "config": {"path": str(source)}}],
    )
    code = main(
        [
            "source",
            "run",
            "policies",
            "--config",
            str(config),
            "--bundle",
            str(bundle),
            "--yes",
            "--json",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["outcome"] == "success"
    assert payload["committed"] is True
    assert payload["commit_sha"] is not None
    assert payload["state"]["last_success_run_id"] == payload["run_id"]


def test_source_run_dry_run_never_commits_and_exits_0(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = _seed_bundle(tmp_path)
    source = _seed_source(tmp_path)
    config = _write_config(
        tmp_path / "sources.json",
        [{"instance_id": "policies", "connector_id": "folder", "config": {"path": str(source)}}],
    )
    code = main(
        [
            "source",
            "run",
            "policies",
            "--config",
            str(config),
            "--bundle",
            str(bundle),
            "--yes",
            "--dry-run",
        ]
    )
    assert code == 0
    assert "rejected" in capsys.readouterr().out
    assert ConnectorStateStore(connectors_root()).load("policies") is None or (
        ConnectorStateStore(connectors_root()).load("policies").cursor is None  # type: ignore[union-attr]
    )


def test_source_run_exits_1_on_a_failed_connector_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = _seed_bundle(tmp_path)
    source = _seed_source(tmp_path)
    config = _write_config(
        tmp_path / "sources.json",
        [{"instance_id": "policies", "connector_id": "folder", "config": {"path": str(source)}}],
    )

    def _boom(*_args: object, **_kwargs: object) -> object:
        raise OSError("simulated I/O failure")

    monkeypatch.setattr("kosha.pipeline.run.ingest_folder", _boom)

    code = main(
        ["source", "run", "policies", "--config", str(config), "--bundle", str(bundle), "--yes"]
    )
    assert code == 1
    assert "policies: failed:" in capsys.readouterr().out


def test_source_run_fails_loud_on_malformed_prior_state(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = _seed_bundle(tmp_path)
    source = _seed_source(tmp_path)
    config = _write_config(
        tmp_path / "sources.json",
        [{"instance_id": "policies", "connector_id": "folder", "config": {"path": str(source)}}],
    )
    state_dir = connectors_root() / "policies"
    state_dir.mkdir(parents=True)
    (state_dir / "state.json").write_text("{not json", encoding="utf-8")

    code = main(
        ["source", "run", "policies", "--config", str(config), "--bundle", str(bundle), "--yes"]
    )
    assert code == 1
    assert "connector state corruption" in capsys.readouterr().err


# --- kosha source status --------------------------------------------------


def test_source_status_reports_never_run_for_a_fresh_instance(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = _seed_source(tmp_path)
    config = _write_config(
        tmp_path / "sources.json",
        [{"instance_id": "policies", "connector_id": "folder", "config": {"path": str(source)}}],
    )
    code = main(["source", "status", "policies", "--config", str(config)])
    assert code == 0
    assert "never run" in capsys.readouterr().out


def test_source_status_json_reports_never_run_state_as_null(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = _seed_source(tmp_path)
    config = _write_config(
        tmp_path / "sources.json",
        [{"instance_id": "policies", "connector_id": "folder", "config": {"path": str(source)}}],
    )
    code = main(["source", "status", "policies", "--config", str(config), "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["state"] is None


def test_source_status_after_a_run_shows_the_committed_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = _seed_bundle(tmp_path)
    source = _seed_source(tmp_path)
    config = _write_config(
        tmp_path / "sources.json",
        [{"instance_id": "policies", "connector_id": "folder", "config": {"path": str(source)}}],
    )
    main(["source", "run", "policies", "--config", str(config), "--bundle", str(bundle), "--yes"])
    capsys.readouterr()

    code = main(["source", "status", "policies", "--config", str(config)])
    assert code == 0
    out = capsys.readouterr().out
    assert "last_success_run_id" in out
    assert "recent_runs (1)" in out
