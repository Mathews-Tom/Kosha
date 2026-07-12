"""Zero-network evidence replay: reconstruction, offline providers, path diffing (M4)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from kosha.evidence import EvidenceStore
from kosha.evidence.model import RunStatus
from kosha.evidence.replay import ReplayError, render_replay_text, replay_run
from kosha.evidence.store import EvidenceCorruptionError
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


def _ingest_with_evidence(
    tmp_path: Path, bundle: Path, store: GitStore, vault: EvidenceStore
) -> str:
    result = ingest(
        _update_source(tmp_path),
        bundle,
        asof=_ASOF,
        source_authority=10,
        git_store=store,
        branch="ingest/evidence",
        evidence_store=vault,
    )
    assert result.committed is True
    assert result.evidence_run is not None
    return result.evidence_run.run.run_id


def test_replay_reconstructs_the_plan_from_stored_evidence_alone(tmp_path: Path) -> None:
    bundle, store = _seed_bundle(tmp_path)
    vault = EvidenceStore(tmp_path / "vault")
    run_id = _ingest_with_evidence(tmp_path, bundle, store, vault)

    report = replay_run(bundle, run_id, store=vault)
    assert report.run_id == run_id
    assert "policies/returns.md" in report.replay_paths


def test_replay_uses_the_offline_deterministic_providers(tmp_path: Path) -> None:
    bundle, store = _seed_bundle(tmp_path)
    vault = EvidenceStore(tmp_path / "vault")
    run_id = _ingest_with_evidence(tmp_path, bundle, store, vault)

    report = replay_run(bundle, run_id, store=vault)
    assert report.current.embedding_provider == "lexical-hash-256"
    assert report.current.generation_provider == "extractive-3"


def test_replay_ignores_ambient_network_provider_env_and_stays_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle, store = _seed_bundle(tmp_path)
    vault = EvidenceStore(tmp_path / "vault")
    run_id = _ingest_with_evidence(tmp_path, bundle, store, vault)

    # Unreachable, fails-fast (nothing listens on port 1); if replay ever resolved a
    # provider from the environment instead of using the fixed offline pair, this
    # would raise a connection error instead of completing. Set *after* seeding so
    # only the replay call itself runs under the poisoned environment.
    monkeypatch.setenv("KOSHA_GEN_BASE_URL", "http://127.0.0.1:1/v1")
    monkeypatch.setenv("KOSHA_GEN_MODEL", "unreachable-model")
    monkeypatch.setenv("KOSHA_EMBED_BASE_URL", "http://127.0.0.1:1/v1")
    monkeypatch.setenv("KOSHA_EMBED_MODEL", "unreachable-model")

    report = replay_run(bundle, run_id, store=vault)
    assert report.current.embedding_provider == "lexical-hash-256"
    assert report.current.generation_provider == "extractive-3"


def test_replay_against_the_already_updated_bundle_reports_index_regen_as_a_replay_difference(
    tmp_path: Path,
) -> None:
    # The original commit already wrote and committed the regenerated index files, so
    # replaying against that same (now-updated) bundle_root finds nothing further to
    # regenerate for them -- a real, honestly labeled replay difference, not corruption.
    bundle, store = _seed_bundle(tmp_path)
    vault = EvidenceStore(tmp_path / "vault")
    run_id = _ingest_with_evidence(tmp_path, bundle, store, vault)

    report = replay_run(bundle, run_id, store=vault)
    assert report.original_commit_sha is not None
    assert report.added_paths == ()
    assert "policies/returns.md" in report.replay_paths
    assert "policies/returns.md" in report.original_paths
    assert set(report.removed_paths) == {"index.md", "policies/index.md"}


def test_replay_with_no_reachable_original_commit_reports_none(tmp_path: Path) -> None:
    bundle, store = _seed_bundle(tmp_path)
    seed_sha = store.current_sha("main")
    vault = EvidenceStore(tmp_path / "vault")
    run_id = _ingest_with_evidence(tmp_path, bundle, store, vault)

    report = replay_run(bundle, run_id, store=vault, ref=seed_sha)
    assert report.original_commit_sha is None
    assert report.original_paths == ()
    assert set(report.added_paths) == set(report.replay_paths)
    assert report.removed_paths == ()


def test_replay_a_missing_run_fails_loud_without_a_live_fetch(tmp_path: Path) -> None:
    bundle, _ = _seed_bundle(tmp_path)
    vault = EvidenceStore(tmp_path / "vault")
    with pytest.raises(EvidenceCorruptionError):
        replay_run(bundle, "no-such-run", store=vault)


def test_replay_a_rejected_run_refuses_with_no_body_to_replay(tmp_path: Path) -> None:
    bundle, store = _seed_bundle(tmp_path)
    vault = EvidenceStore(tmp_path / "vault")
    # A source whose only content matches the secret scanner never gets accepted evidence.
    secret_source = tmp_path / "secret-source"
    (secret_source / "policies").mkdir(parents=True)
    (secret_source / "policies" / "leak.md").write_text(
        "AWS_SECRET_ACCESS_KEY=AKIAABCDEFGHIJKLMNOP/verysecretvaluehere1234567890abcd\n",
        encoding="utf-8",
    )
    result = ingest(
        secret_source,
        bundle,
        asof=_ASOF,
        dry_run=True,
        git_store=store,
        evidence_store=vault,
    )
    assert result.evidence_run is not None
    assert result.evidence_run.run.status is RunStatus.REJECTED
    # The pipeline never persists a rejected run's manifest (persist_evidence_run
    # is a no-op for it); write it directly to exercise replay's own refusal.
    vault.write_run(result.evidence_run.run)

    with pytest.raises(ReplayError):
        replay_run(bundle, result.evidence_run.run.run_id, store=vault)


def test_render_replay_text_reports_zero_network_and_pipeline_identity(tmp_path: Path) -> None:
    bundle, store = _seed_bundle(tmp_path)
    vault = EvidenceStore(tmp_path / "vault")
    run_id = _ingest_with_evidence(tmp_path, bundle, store, vault)

    rendered = render_replay_text(replay_run(bundle, run_id, store=vault))
    assert "network calls: 0" in rendered
    assert "current providers: embedding=lexical-hash-256 generation=extractive-3" in rendered
    assert "path differences vs. the original commit (replay difference, not corruption):" in (
        rendered
    )
    assert "    - index.md" in rendered
