"""Evidence integrity verification: clean manifests, corruption, legacy separation (M4)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from kosha.evidence import EvidenceStore
from kosha.evidence.paths import object_path
from kosha.evidence.verify import render_verification_text, verify_evidence
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


def test_an_empty_vault_reports_ok_with_nothing_to_verify(tmp_path: Path) -> None:
    bundle, _ = _seed_bundle(tmp_path)
    vault = EvidenceStore(tmp_path / "vault")
    report = verify_evidence(bundle, store=vault)
    assert report.ok is True
    assert report.runs == ()
    assert report.commits == ()
    assert report.legacy_commit_count == 0


def test_a_clean_accepted_run_and_commit_verify_ok(tmp_path: Path) -> None:
    bundle, store = _seed_bundle(tmp_path)
    vault = EvidenceStore(tmp_path / "vault")
    run_id = _ingest_with_evidence(tmp_path, bundle, store, vault)

    report = verify_evidence(bundle, store=vault)
    assert report.ok is True
    assert len(report.runs) == 1
    assert report.runs[0].run_id == run_id
    assert report.runs[0].ok is True
    assert report.runs[0].evidence_object_count == 1
    assert len(report.commits) == 1
    assert report.commits[0].ok is True
    assert report.commits[0].source_run == run_id
    assert report.corrupt_run_count == 0
    assert report.unresolved_commit_count == 0


def test_a_bit_flipped_object_fails_verification_non_zero(tmp_path: Path) -> None:
    bundle, store = _seed_bundle(tmp_path)
    vault = EvidenceStore(tmp_path / "vault")
    run_id = _ingest_with_evidence(tmp_path, bundle, store, vault)
    run = vault.read_run(run_id)
    digest = run.evidence[0].sha256
    path = object_path(vault.root, digest)
    corrupted = bytearray(path.read_bytes())
    corrupted[0] ^= 0xFF
    path.write_bytes(bytes(corrupted))

    report = verify_evidence(bundle, store=vault)
    assert report.ok is False
    assert report.corrupt_run_count == 1
    assert report.runs[0].ok is False
    assert report.runs[0].error is not None
    assert report.unresolved_commit_count == 1
    assert report.commits[0].ok is False


def test_a_missing_object_fails_verification_non_zero(tmp_path: Path) -> None:
    bundle, store = _seed_bundle(tmp_path)
    vault = EvidenceStore(tmp_path / "vault")
    run_id = _ingest_with_evidence(tmp_path, bundle, store, vault)
    run = vault.read_run(run_id)
    digest = run.evidence[0].sha256
    object_path(vault.root, digest).unlink()

    report = verify_evidence(bundle, store=vault)
    assert report.ok is False
    assert report.corrupt_run_count == 1
    assert report.unresolved_commit_count == 1


def test_a_legacy_ingest_commit_is_reported_separately_not_fabricated(tmp_path: Path) -> None:
    bundle, store = _seed_bundle(tmp_path)
    (bundle / "policies" / "shipping.md").write_text(
        "---\ntype: policy\ntitle: Shipping\n---\nShips within 3 days.\n", encoding="utf-8"
    )
    store.commit(
        ["policies/shipping.md"],
        "feat(kosha): ingest legacy\n\n- create policies/shipping.md",
    )
    vault = EvidenceStore(tmp_path / "vault")

    report = verify_evidence(bundle, store=vault)
    assert report.ok is True
    assert report.legacy_commit_count == 1
    assert report.commits == ()  # legacy commits never enter the verified-trailer list


def test_render_verification_text_reports_ok(tmp_path: Path) -> None:
    bundle, store = _seed_bundle(tmp_path)
    vault = EvidenceStore(tmp_path / "vault")
    _ingest_with_evidence(tmp_path, bundle, store, vault)

    report = verify_evidence(bundle, store=vault)
    rendered = render_verification_text(report)
    assert "OK" in rendered
    assert "runs:    1 stored (0 corrupt)" in rendered


def test_render_verification_text_reports_corruption(tmp_path: Path) -> None:
    bundle, store = _seed_bundle(tmp_path)
    vault = EvidenceStore(tmp_path / "vault")
    run_id = _ingest_with_evidence(tmp_path, bundle, store, vault)
    run = vault.read_run(run_id)
    object_path(vault.root, run.evidence[0].sha256).unlink()

    rendered = render_verification_text(verify_evidence(bundle, store=vault))
    assert "CORRUPTION DETECTED" in rendered
    assert run_id in rendered
