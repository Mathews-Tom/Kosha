"""Versioned bundle releases: immutable tags over a validated snapshot (M8 PR-5)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from kosha.git_store import GitError, GitStore
from kosha.release import ReleaseError, create_release, release_tag_name

_ASOF = datetime(2026, 6, 28, tzinfo=UTC)

_CONFORMANT_CONCEPT = """---
type: policy
title: Returns
description: When and how customers may return products.
timestamp: 2026-06-27T10:00:00Z
---

Standard returns are accepted within 30 days of delivery.
"""

_INDEX = """---
okf_version: '0.1'
---

# Concepts

* [Returns](/concepts/returns.md) - Standard returns policy.
"""

_NON_CONFORMANT_CONCEPT = """---
title: missing the required type field
---

body
"""


def _conformant_bundle(tmp_path: Path) -> GitStore:
    store = GitStore.init(tmp_path)
    (tmp_path / "concepts").mkdir()
    (tmp_path / "concepts" / "returns.md").write_text(_CONFORMANT_CONCEPT, encoding="utf-8")
    (tmp_path / "index.md").write_text(_INDEX, encoding="utf-8")
    store.commit(["concepts/returns.md", "index.md"], "chore: seed")
    return store


def test_release_tag_name_is_prefixed() -> None:
    assert release_tag_name("v1") == "release/v1"


def test_create_release_tags_head_and_returns_a_record(tmp_path: Path) -> None:
    store = _conformant_bundle(tmp_path)
    head_sha = store.current_sha("HEAD")

    record = create_release(store, tmp_path, "v1", asof=_ASOF)

    assert record.tag == "release/v1"
    assert record.ref == head_sha
    assert record.concept_count == 1
    assert record.warning_count == 0
    assert record.export_path is None
    assert store.tag_exists("release/v1")
    assert store.current_sha("release/v1") == head_sha


def test_create_release_refuses_a_non_conformant_bundle(tmp_path: Path) -> None:
    store = GitStore.init(tmp_path)
    (tmp_path / "bad.md").write_text(_NON_CONFORMANT_CONCEPT, encoding="utf-8")
    store.commit(["bad.md"], "chore: seed bad")

    with pytest.raises(ReleaseError, match="not OKF-conformant"):
        create_release(store, tmp_path, "v1", asof=_ASOF)

    assert not store.tag_exists("release/v1")


def test_create_release_refuses_to_re_tag_an_existing_version(tmp_path: Path) -> None:
    store = _conformant_bundle(tmp_path)
    create_release(store, tmp_path, "v1", asof=_ASOF)

    with pytest.raises(ReleaseError, match="release/v1"):
        create_release(store, tmp_path, "v1", asof=_ASOF)


def test_create_release_a_new_version_after_a_new_commit_points_at_the_new_head(
    tmp_path: Path,
) -> None:
    store = _conformant_bundle(tmp_path)
    create_release(store, tmp_path, "v1", asof=_ASOF)

    (tmp_path / "concepts" / "returns.md").write_text(
        _CONFORMANT_CONCEPT.replace("30 days", "60 days"), encoding="utf-8"
    )
    store.commit(["concepts/returns.md"], "feat: extend window")
    record = create_release(store, tmp_path, "v2", asof=_ASOF)

    assert record.ref == store.current_sha("HEAD")
    assert record.ref != store.current_sha("release/v1")
    # v1 is untouched by cutting v2 -- immutable, never force-moved.
    assert store.current_sha("release/v1") != store.current_sha("release/v2")


def test_create_release_export_writes_a_zip_archive(tmp_path: Path) -> None:
    store = _conformant_bundle(tmp_path)
    out = tmp_path.parent / "export" / "v1.zip"

    record = create_release(store, tmp_path, "v1", asof=_ASOF, export_path=out)

    assert record.export_path == str(out)
    assert out.is_file()
    assert out.read_bytes()[:2] == b"PK"  # zip magic bytes


def test_create_release_export_is_reproducible_across_tags_of_the_same_ref(
    tmp_path: Path,
) -> None:
    store = _conformant_bundle(tmp_path)
    out_a = tmp_path.parent / "a.zip"
    out_b = tmp_path.parent / "b.zip"

    create_release(store, tmp_path, "v1", asof=_ASOF, export_path=out_a)
    create_release(store, tmp_path, "v2", asof=_ASOF, export_path=out_b)

    # Same underlying tree -> byte-identical archives regardless of tag name.
    a_digest = hashlib.sha256(out_a.read_bytes()).digest()
    b_digest = hashlib.sha256(out_b.read_bytes()).digest()
    assert a_digest == b_digest


def test_export_archive_rejects_an_unsupported_suffix(tmp_path: Path) -> None:
    store = _conformant_bundle(tmp_path)
    with pytest.raises(GitError, match="unsupported archive format"):
        store.export_archive("HEAD", tmp_path.parent / "out.tar.gz")
