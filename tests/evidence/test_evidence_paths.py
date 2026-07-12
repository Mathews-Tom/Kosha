"""Evidence path resolution: private root, digest/run-id validation, traversal (M2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from kosha.evidence.paths import (
    InvalidDigestError,
    InvalidRunIdError,
    bundle_identity,
    evidence_root,
    kosha_home,
    manifest_path,
    object_path,
    validate_digest,
    validate_run_id,
)

_VALID_DIGEST = "a" * 64


def test_kosha_home_defaults_under_user_home() -> None:
    assert kosha_home(env={}) == Path.home() / ".kosha"


def test_kosha_home_honors_env_override() -> None:
    assert kosha_home(env={"KOSHA_HOME": "/private/kosha-data"}) == Path("/private/kosha-data")


def test_bundle_identity_is_stable_for_the_same_path(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    assert bundle_identity(bundle) == bundle_identity(bundle)


def test_bundle_identity_differs_for_different_paths(tmp_path: Path) -> None:
    assert bundle_identity(tmp_path / "a") != bundle_identity(tmp_path / "b")


def test_bundle_identity_is_a_digest_not_the_path(tmp_path: Path) -> None:
    bundle = tmp_path / "secret-project-name"
    identity = bundle_identity(bundle)
    assert "secret-project-name" not in identity
    assert validate_digest(identity) == identity


def test_evidence_root_lives_under_kosha_home_evidence_bundle_identity(tmp_path: Path) -> None:
    home = tmp_path / "home"
    bundle = tmp_path / "repo" / "bundle"
    root = evidence_root(bundle, home=home)
    assert root == home / "evidence" / bundle_identity(bundle)


def test_evidence_root_is_injectable_without_touching_real_home(tmp_path: Path) -> None:
    root_a = evidence_root(tmp_path / "bundle", home=tmp_path / "home-a")
    root_b = evidence_root(tmp_path / "bundle", home=tmp_path / "home-b")
    assert root_a != root_b
    assert str(tmp_path / "home-a") in str(root_a)


def test_validate_digest_accepts_lowercase_sha256() -> None:
    assert validate_digest(_VALID_DIGEST) == _VALID_DIGEST


@pytest.mark.parametrize(
    "bad",
    [
        "A" * 64,  # uppercase
        "a" * 63,  # too short
        "a" * 65,  # too long
        "g" * 64,  # non-hex
        "../../etc/passwd",
        "",
    ],
)
def test_validate_digest_rejects_anything_else(bad: str) -> None:
    with pytest.raises(InvalidDigestError):
        validate_digest(bad)


def test_object_path_is_rooted_under_objects(tmp_path: Path) -> None:
    path = object_path(tmp_path, _VALID_DIGEST)
    assert path == tmp_path / "objects" / _VALID_DIGEST
    assert path.is_relative_to(tmp_path)


@pytest.mark.parametrize(
    "traversal",
    ["../../../etc/passwd", "../escape", "a/../../b", "a/b"],
)
def test_object_path_rejects_traversal_digests(tmp_path: Path, traversal: str) -> None:
    with pytest.raises(InvalidDigestError):
        object_path(tmp_path, traversal)


def test_validate_run_id_accepts_a_plain_identifier() -> None:
    assert validate_run_id("run-2026-07-12-0001") == "run-2026-07-12-0001"


@pytest.mark.parametrize(
    "bad",
    ["", ".", "..", "../escape", "a/b", "a/../b", "/etc/passwd", "a\x00b"],
)
def test_validate_run_id_rejects_traversal_and_empty(bad: str) -> None:
    with pytest.raises(InvalidRunIdError):
        validate_run_id(bad)


def test_manifest_path_cannot_escape_the_vault_root(tmp_path: Path) -> None:
    with pytest.raises(InvalidRunIdError):
        manifest_path(tmp_path, "../../outside")
    safe = manifest_path(tmp_path, "run-1")
    assert safe.is_relative_to(tmp_path)
    assert safe == tmp_path / "runs" / "run-1.json"
