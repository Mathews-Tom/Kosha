"""``kosha release`` at the CLI layer (M8 PR-5).

Complements the direct unit tests of ``create_release``
(``tests/release/test_release.py``) with the CLI wiring: exit codes for
refusal (non-conformant, duplicate tag) versus infra errors (bad path).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kosha.cli import main
from kosha.git_store import GitStore

_CONFORMANT_CONCEPT = """---
type: policy
title: Returns
description: When and how customers may return products.
timestamp: 2026-06-27T10:00:00Z
---

Standard returns are accepted within 30 days of delivery.
"""

_NON_CONFORMANT_CONCEPT = """---
title: missing the required type field
---

body
"""


def _conformant_bundle(root: Path) -> GitStore:
    store = GitStore.init(root)
    (root / "returns.md").write_text(_CONFORMANT_CONCEPT, encoding="utf-8")
    store.commit(["returns.md"], "chore: seed")
    return store


def test_release_rejects_a_missing_bundle_directory(tmp_path: Path) -> None:
    code = main(["release", str(tmp_path / "nope"), "--tag", "v1"])
    assert code == 2


def test_release_rejects_a_non_git_bundle_directory(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    code = main(["release", str(bundle), "--tag", "v1"])
    assert code == 2


def test_release_tags_a_conformant_bundle(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = tmp_path / "bundle"
    store = _conformant_bundle(bundle)

    code = main(["release", str(bundle), "--tag", "v1"])

    assert code == 0
    assert "Released release/v1" in capsys.readouterr().out
    assert store.tag_exists("release/v1")


def test_release_json_reports_the_record(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = tmp_path / "bundle"
    _conformant_bundle(bundle)

    code = main(["release", str(bundle), "--tag", "v1", "--json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["tag"] == "release/v1"
    assert payload["concept_count"] == 1
    assert payload["export_path"] is None


def test_release_refuses_a_non_conformant_bundle(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = tmp_path / "bundle"
    store = GitStore.init(bundle)
    (bundle / "bad.md").write_text(_NON_CONFORMANT_CONCEPT, encoding="utf-8")
    store.commit(["bad.md"], "chore: seed bad")

    code = main(["release", str(bundle), "--tag", "v1"])

    assert code == 1
    assert "not OKF-conformant" in capsys.readouterr().err
    assert not store.tag_exists("release/v1")


def test_release_refuses_to_re_tag_an_existing_version(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = tmp_path / "bundle"
    _conformant_bundle(bundle)
    assert main(["release", str(bundle), "--tag", "v1"]) == 0

    code = main(["release", str(bundle), "--tag", "v1"])

    assert code == 1
    assert "release/v1" in capsys.readouterr().err


def test_release_exports_an_archive_when_out_is_given(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = tmp_path / "bundle"
    _conformant_bundle(bundle)
    out = tmp_path / "export" / "v1.zip"

    code = main(["release", str(bundle), "--tag", "v1", "--out", str(out)])

    assert code == 0
    assert out.is_file()
    assert f"Exported to {out}" in capsys.readouterr().out
