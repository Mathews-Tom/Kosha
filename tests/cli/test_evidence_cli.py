"""``kosha evidence verify|show|replay`` at the CLI layer (M4).

Every scenario relies on the autouse ``KOSHA_HOME`` redirect in
``tests/conftest.py``: ``ingest()`` and the CLI both resolve the same default,
per-test-isolated evidence vault, so no test needs to inject an explicit
``EvidenceStore``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from kosha.cli import main
from kosha.evidence import EvidenceStore, evidence_root
from kosha.evidence.paths import object_path
from kosha.git_store import GitStore
from kosha.pipeline import ingest

_ASOF = datetime(2026, 6, 28, tzinfo=UTC)


def _seed_bundle(tmp_path: Path) -> tuple[Path, GitStore]:
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
    return bundle, store


def _update_source(tmp_path: Path, *, days: int = 60) -> Path:
    source = tmp_path / "source"
    (source / "policies").mkdir(parents=True)
    (source / "policies" / "returns.md").write_text(
        f"# Returns\n\nStandard returns are accepted within {days} days of delivery.\n",
        encoding="utf-8",
    )
    return source


def _seed_evidence(tmp_path: Path, bundle: Path, store: GitStore) -> str:
    result = ingest(
        _update_source(tmp_path),
        bundle,
        asof=_ASOF,
        source_authority=10,
        git_store=store,
        branch="ingest/evidence",
    )
    assert result.committed is True
    assert result.evidence_run is not None
    return result.evidence_run.run.run_id


def test_evidence_with_no_subcommand_prints_usage_and_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["evidence"])
    assert code == 2
    assert "verify, show, replay" in capsys.readouterr().err


def test_evidence_verify_rejects_a_missing_bundle_directory(tmp_path: Path) -> None:
    code = main(["evidence", "verify", str(tmp_path / "nope")])
    assert code == 2


def test_evidence_verify_reports_ok_after_a_clean_ingest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle, store = _seed_bundle(tmp_path)
    _seed_evidence(tmp_path, bundle, store)

    code = main(["evidence", "verify", str(bundle)])
    assert code == 0
    assert "OK" in capsys.readouterr().out


def test_evidence_verify_json_reports_ok(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle, store = _seed_bundle(tmp_path)
    run_id = _seed_evidence(tmp_path, bundle, store)

    code = main(["evidence", "verify", str(bundle), "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["runs"][0]["run_id"] == run_id


def test_evidence_verify_detects_corruption_and_exits_non_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle, store = _seed_bundle(tmp_path)
    run_id = _seed_evidence(tmp_path, bundle, store)
    vault = EvidenceStore(evidence_root(bundle))
    run = vault.read_run(run_id)
    object_path(vault.root, run.evidence[0].sha256).unlink()

    code = main(["evidence", "verify", str(bundle), "--json"])
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False


def test_evidence_show_defaults_to_metadata_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle, store = _seed_bundle(tmp_path)
    run_id = _seed_evidence(tmp_path, bundle, store)

    code = main(["evidence", "show", str(bundle), run_id])
    assert code == 0
    out = capsys.readouterr().out
    assert run_id in out
    assert "content:" not in out
    assert "60 days" not in out


def test_evidence_show_json_defaults_to_metadata_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle, store = _seed_bundle(tmp_path)
    run_id = _seed_evidence(tmp_path, bundle, store)

    code = main(["evidence", "show", str(bundle), run_id, "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert "text" not in payload["evidence"][0]


def test_evidence_show_content_flag_prints_the_evidence_text(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle, store = _seed_bundle(tmp_path)
    run_id = _seed_evidence(tmp_path, bundle, store)

    code = main(["evidence", "show", str(bundle), run_id, "--content"])
    assert code == 0
    assert "60 days" in capsys.readouterr().out


def test_evidence_show_content_json_includes_the_evidence_text(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle, store = _seed_bundle(tmp_path)
    run_id = _seed_evidence(tmp_path, bundle, store)

    code = main(["evidence", "show", str(bundle), run_id, "--content", "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert "60 days" in payload["evidence"][0]["text"]


def test_evidence_show_missing_run_fails_loud(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle, _ = _seed_bundle(tmp_path)
    code = main(["evidence", "show", str(bundle), "no-such-run"])
    assert code == 1
    assert "evidence corruption" in capsys.readouterr().err


def test_evidence_replay_reports_zero_network_and_offline_providers(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle, store = _seed_bundle(tmp_path)
    run_id = _seed_evidence(tmp_path, bundle, store)

    code = main(["evidence", "replay", str(bundle), run_id])
    assert code == 0
    out = capsys.readouterr().out
    assert "network calls: 0" in out
    assert "embedding=lexical-hash-256" in out


def test_evidence_replay_json_reports_current_providers_and_paths(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle, store = _seed_bundle(tmp_path)
    run_id = _seed_evidence(tmp_path, bundle, store)

    code = main(["evidence", "replay", str(bundle), run_id, "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["current_providers"]["embedding"] == "lexical-hash-256"
    assert payload["original_provider_identity_recorded"] is False
    assert "policies/returns.md" in payload["replay_paths"]


def test_evidence_replay_missing_run_fails_loud(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle, _ = _seed_bundle(tmp_path)
    code = main(["evidence", "replay", str(bundle), "no-such-run"])
    assert code == 1
    assert "evidence corruption" in capsys.readouterr().err
