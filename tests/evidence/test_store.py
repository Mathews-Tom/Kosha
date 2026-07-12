"""Content-addressed evidence store: dedup, atomicity, corruption, permissions (M2)."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from datetime import UTC, datetime
from pathlib import Path

import pytest

from kosha.evidence.model import EvidenceDocument, RunStatus, SourceRun
from kosha.evidence.paths import object_path
from kosha.evidence.store import EvidenceConflictError, EvidenceCorruptionError, EvidenceStore


def _store(tmp_path: Path) -> EvidenceStore:
    return EvidenceStore(tmp_path / "vault")


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _document(text: str, *, source_id: str = "src-1") -> EvidenceDocument:
    return EvidenceDocument(
        sha256=_digest(text),
        source_id=source_id,
        location="https://example.test/doc",
        retrieved_at=datetime(2026, 7, 12, tzinfo=UTC),
        media_type="text/markdown",
        normalized_text_bytes=len(text.encode("utf-8")),
        normalization_version="v1",
    )


def _run(
    *,
    run_id: str = "run-1",
    status: RunStatus = RunStatus.ACCEPTED,
    evidence: tuple[EvidenceDocument, ...] = (),
    detector_names: tuple[str, ...] = (),
) -> SourceRun:
    return SourceRun(
        run_id=run_id,
        bundle_identity="b" * 64,
        source_instance_id="instance-1",
        adapter="folder",
        adapter_version="1",
        started_at=datetime(2026, 7, 12, 0, 0, tzinfo=UTC),
        completed_at=datetime(2026, 7, 12, 0, 1, tzinfo=UTC),
        status=status,
        evidence=evidence,
        detector_names=detector_names,
    )


# --- content addressing -----------------------------------------------------


def test_identical_bytes_produce_the_same_digest(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = store.put_object("hello world")
    second = store.put_object("hello world")
    assert first == second == _digest("hello world")


def test_one_byte_change_produces_a_different_digest(tmp_path: Path) -> None:
    store = _store(tmp_path)
    a = store.put_object("hello world")
    b = store.put_object("hello worle")
    assert a != b


def test_insert_is_idempotent_on_disk(tmp_path: Path) -> None:
    store = _store(tmp_path)
    digest = store.put_object("payload")
    path = object_path(store.root, digest)
    first_mtime = path.stat().st_mtime_ns
    store.put_object("payload")
    assert path.stat().st_mtime_ns == first_mtime or path.read_text() == "payload"
    assert store.read_object(digest) == "payload"


def test_digest_conflict_with_differing_on_disk_bytes_fails_loud(tmp_path: Path) -> None:
    store = _store(tmp_path)
    digest = store.put_object("original")
    object_path(store.root, digest).write_bytes(b"corrupted-but-same-name")
    with pytest.raises(EvidenceConflictError):
        store.put_object("original")


def test_has_object_reflects_store_state(tmp_path: Path) -> None:
    store = _store(tmp_path)
    digest = _digest("not stored")
    assert store.has_object(digest) is False
    stored_digest = store.put_object("not stored")
    assert stored_digest == digest
    assert store.has_object(digest) is True


# --- corruption handling -----------------------------------------------------


def test_reading_a_missing_object_fails_loud(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with pytest.raises(EvidenceCorruptionError):
        store.read_object(_digest("never written"))


def test_reading_a_bit_flipped_object_fails_loud(tmp_path: Path) -> None:
    store = _store(tmp_path)
    digest = store.put_object("payload")
    object_path(store.root, digest).write_bytes(b"tampered")
    with pytest.raises(EvidenceCorruptionError):
        store.read_object(digest)


def test_reading_a_missing_manifest_fails_loud(tmp_path: Path) -> None:
    store = _store(tmp_path)
    with pytest.raises(EvidenceCorruptionError):
        store.read_run("no-such-run")


def test_malformed_manifest_json_fails_loud_not_empty_state(tmp_path: Path) -> None:
    store = _store(tmp_path)
    manifest = store.root / "runs" / "run-1.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{not-json", encoding="utf-8")
    with pytest.raises(EvidenceCorruptionError):
        store.read_run("run-1")


def test_manifest_missing_required_field_fails_loud(tmp_path: Path) -> None:
    store = _store(tmp_path)
    manifest = store.root / "runs" / "run-1.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"run_id": "run-1"}), encoding="utf-8")
    with pytest.raises(EvidenceCorruptionError):
        store.read_run("run-1")


def test_manifest_referencing_a_missing_object_fails_loud_on_read(tmp_path: Path) -> None:
    store = _store(tmp_path)
    document = _document("orphaned reference")
    manifest = store.root / "runs" / "run-1.json"
    manifest.parent.mkdir(parents=True)
    run = _run(evidence=(document,))
    manifest.write_text(
        json.dumps(run.model_dump(mode="json"), sort_keys=True), encoding="utf-8"
    )
    with pytest.raises(EvidenceCorruptionError):
        store.read_run("run-1")


# --- manifest / object ordering and atomicity --------------------------------


def test_write_run_rejects_a_run_referencing_a_missing_object(tmp_path: Path) -> None:
    store = _store(tmp_path)
    document = _document("never persisted")
    run = _run(evidence=(document,))
    with pytest.raises(EvidenceCorruptionError):
        store.write_run(run)
    assert not (store.root / "runs" / "run-1.json").exists()


def test_write_run_succeeds_once_referenced_objects_exist(tmp_path: Path) -> None:
    store = _store(tmp_path)
    text = "accepted body"
    document = _document(text)
    store.put_object(text)
    run = _run(evidence=(document,))
    path = store.write_run(run)
    assert path.exists()
    loaded = store.read_run("run-1")
    assert loaded.evidence[0].sha256 == document.sha256


def test_interrupted_manifest_write_leaves_no_dangling_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _store(tmp_path)
    text = "interrupted body"
    document = _document(text)
    store.put_object(text)
    run = _run(evidence=(document,))

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated crash mid-replace")

    monkeypatch.setattr(os, "replace", _boom)
    with pytest.raises(OSError, match="simulated crash mid-replace"):
        store.write_run(run)

    runs_dir = store.root / "runs"
    leftover = list(runs_dir.glob("*")) if runs_dir.exists() else []
    assert leftover == []
    monkeypatch.undo()
    with pytest.raises(EvidenceCorruptionError):
        store.read_run("run-1")


# --- rejected-run body absence ------------------------------------------------


def test_rejected_run_model_rejects_carrying_evidence() -> None:
    with pytest.raises(ValueError, match="must not retain a source body"):
        _run(status=RunStatus.REJECTED, evidence=(_document("leaked body"),))


def test_rejected_run_manifest_has_detector_names_but_no_body(tmp_path: Path) -> None:
    store = _store(tmp_path)
    run = _run(status=RunStatus.REJECTED, detector_names=("github-token",))
    path = store.write_run(run)
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["detector_names"] == ["github-token"]
    assert raw["evidence"] == []
    serialized = path.read_text(encoding="utf-8")
    assert "leaked" not in serialized


# --- determinism --------------------------------------------------------------


def test_manifest_serialization_is_byte_stable(tmp_path: Path) -> None:
    store_a = _store(tmp_path)
    text = "stable body"
    store_a.put_object(text)
    run = _run(evidence=(_document(text),))
    path_a = store_a.write_run(run)
    bytes_a = path_a.read_bytes()

    store_b = EvidenceStore(tmp_path / "vault-b")
    store_b.put_object(text)
    path_b = store_b.write_run(run)
    bytes_b = path_b.read_bytes()

    assert bytes_a == bytes_b


# --- permissions ---------------------------------------------------------------


@pytest.mark.skipif(os.name != "posix", reason="permission bits require a POSIX filesystem")
def test_object_file_permissions_are_owner_only(tmp_path: Path) -> None:
    store = _store(tmp_path)
    digest = store.put_object("secret-ish body")
    mode = stat.S_IMODE(object_path(store.root, digest).stat().st_mode)
    assert mode == 0o600


@pytest.mark.skipif(os.name != "posix", reason="permission bits require a POSIX filesystem")
def test_object_directory_permissions_are_owner_only(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.put_object("payload")
    for directory in (store.root, store.root / "objects"):
        mode = stat.S_IMODE(directory.stat().st_mode)
        assert mode == 0o700


@pytest.mark.skipif(os.name != "posix", reason="permission bits require a POSIX filesystem")
def test_manifest_file_permissions_are_owner_only(tmp_path: Path) -> None:
    store = _store(tmp_path)
    text = "manifest body"
    store.put_object(text)
    run = _run(evidence=(_document(text),))
    path = store.write_run(run)
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600
