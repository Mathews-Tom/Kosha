"""``kosha recover backups|restore|reindex`` at the CLI layer (M8 PR-4).

Complements the direct unit tests of the recovery primitives
(``tests/recovery/test_recovery.py``) with the CLI wiring: dry-run-by-default,
the explicit ``--apply`` gate, and the audit-log flag.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from kosha.cli import main
from kosha.git_store import GitStore

_CONCEPT = """---
type: policy
title: Returns
description: When and how customers may return products.
timestamp: 2026-06-27T10:00:00Z
---

Standard returns are accepted within 30 days of delivery.
"""


def _seeded_bundle(root: Path) -> GitStore:
    store = GitStore.init(root)
    (root / "returns.md").write_text(_CONCEPT, encoding="utf-8")
    store.commit(["returns.md"], "chore: seed")
    return store


def test_recover_rejects_a_missing_bundle_directory(tmp_path: Path) -> None:
    code = main(["recover", "backups", str(tmp_path / "nope")])
    assert code == 2


def test_recover_rejects_a_non_git_bundle_directory(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    code = main(["recover", "backups", str(bundle)])
    assert code == 2


def test_recover_with_no_subcommand_prints_usage_and_exits_2(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(["recover"])
    assert code == 2
    assert "usage" in capsys.readouterr().err


def test_recover_backups_lists_tags(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bundle = tmp_path / "bundle"
    store = _seeded_bundle(bundle)
    store.tag_daily_backup(date(2026, 6, 28))

    code = main(["recover", "backups", str(bundle)])

    assert code == 0
    assert "backup/2026-06-28" in capsys.readouterr().out


def test_recover_backups_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bundle = tmp_path / "bundle"
    store = _seeded_bundle(bundle)
    tag = store.tag_daily_backup(date(2026, 6, 28))

    code = main(["recover", "backups", str(bundle), "--json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    expected = [{"name": tag, "sha": store.current_sha(tag), "date": "2026-06-28"}]
    assert payload["backups"] == expected


def test_recover_restore_dry_run_never_mutates(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = tmp_path / "bundle"
    store = _seeded_bundle(bundle)
    tag = store.tag_daily_backup(date(2026, 6, 28))
    (bundle / "returns.md").write_text(_CONCEPT.replace("30 days", "60 days"), encoding="utf-8")
    store.commit(["returns.md"], "feat: extend window")

    code = main(["recover", "restore", str(bundle), "--tag", tag])

    assert code == 0
    out = capsys.readouterr().out
    assert "M returns.md" in out
    assert "dry run: no changes written" in out
    assert store.head_branch() == "main"
    assert "60 days" in (bundle / "returns.md").read_text(encoding="utf-8")


def test_recover_restore_apply_mutates_and_writes_audit_log(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = tmp_path / "bundle"
    store = _seeded_bundle(bundle)
    tag = store.tag_daily_backup(date(2026, 6, 28))
    (bundle / "returns.md").write_text(_CONCEPT.replace("30 days", "60 days"), encoding="utf-8")
    store.commit(["returns.md"], "feat: extend window")
    audit_log = tmp_path / "audit.jsonl"

    code = main(
        [
            "recover",
            "restore",
            str(bundle),
            "--tag",
            tag,
            "--apply",
            "--audit-log",
            str(audit_log),
        ]
    )

    assert code == 0
    assert "restored 1 file(s)" in capsys.readouterr().out
    assert store.head_branch() != "main"
    assert "30 days" in (bundle / "returns.md").read_text(encoding="utf-8")
    record = json.loads(audit_log.read_text(encoding="utf-8").splitlines()[0])
    assert record["action"] == "restore"
    assert record["applied"] is True
    assert record["source_ref"] == tag


def test_recover_restore_unknown_tag_fails_loud_without_mutating(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = tmp_path / "bundle"
    store = _seeded_bundle(bundle)

    code = main(["recover", "restore", str(bundle), "--tag", "backup/2099-01-01", "--apply"])

    assert code == 2
    assert "backup/2099-01-01" in capsys.readouterr().err
    assert store.head_branch() == "main"


def test_recover_restore_json_reports_the_plan_and_record(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = tmp_path / "bundle"
    store = _seeded_bundle(bundle)
    tag = store.tag_daily_backup(date(2026, 6, 28))
    (bundle / "returns.md").write_text(_CONCEPT.replace("30 days", "60 days"), encoding="utf-8")
    store.commit(["returns.md"], "feat: extend window")

    code = main(["recover", "restore", str(bundle), "--tag", tag, "--json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["tag"] == tag
    assert payload["applied"] is False
    assert payload["record"] is None
    assert payload["changes"] == [{"status": "M", "path": "returns.md"}]


def test_recover_reindex_dry_run_then_apply(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = tmp_path / "bundle"
    _seeded_bundle(bundle)

    dry_code = main(["recover", "reindex", str(bundle)])
    assert dry_code == 0
    dry_out = capsys.readouterr().out
    assert "create index.md" in dry_out
    assert "dry run: no changes written" in dry_out
    assert not (bundle / "index.md").is_file()

    apply_code = main(["recover", "reindex", str(bundle), "--apply"])
    assert apply_code == 0
    assert "reindexed 1 file(s)" in capsys.readouterr().out
    assert (bundle / "index.md").is_file()


def test_recover_reindex_with_no_drift_reports_nothing_to_do(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = tmp_path / "bundle"
    store = _seeded_bundle(bundle)
    main(["recover", "reindex", str(bundle), "--apply"])
    branch = store.head_branch()
    store.switch(branch)

    code = main(["recover", "reindex", str(bundle)])

    assert code == 0
    assert "No drift" in capsys.readouterr().out
