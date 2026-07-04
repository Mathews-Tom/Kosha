"""``kosha ingest --review``: per-item approve/reject at the CLI layer (M8 PR-3).

Complements the direct unit tests of ``request_item_decisions``
(``tests/approve/test_itemreview.py``) and ``commit_plan``
(``tests/pipeline/test_pipeline.py``) with the CLI wiring itself: the
``--yes``/``--review`` mutual exclusion, and the default-safe outcome when
review is requested without an interactive terminal to answer from.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kosha.cli import main
from kosha.git_store import GitStore


def _seed_bundle(root: Path) -> None:
    store = GitStore.init(root)
    (root / "index.md").write_text('okf_version: "0.1"\n', encoding="utf-8")
    store.commit(["index.md"], "chore: seed")


def _source(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "widget.md").write_text(
        "# Widget Policy\n\nWidgets ship within 3 business days of order confirmation.\n",
        encoding="utf-8",
    )
    return root


def test_yes_and_review_are_mutually_exclusive(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    source = _source(tmp_path / "source")
    _seed_bundle(bundle)
    with pytest.raises(SystemExit) as exc_info:
        main(["ingest", str(source), "--bundle", str(bundle), "--yes", "--review"])
    assert exc_info.value.code == 2


def test_review_without_a_tty_defaults_safe_and_commits_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = tmp_path / "bundle"
    source = _source(tmp_path / "source")
    _seed_bundle(bundle)
    store = GitStore(bundle)
    main_sha = store.current_sha("HEAD")

    code = main(["ingest", str(source), "--bundle", str(bundle), "--review"])

    assert code == 0
    assert store.current_sha("HEAD") == main_sha  # nothing committed
    assert "not approved" in capsys.readouterr().out


def test_review_json_reports_no_commit_when_non_interactive(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = tmp_path / "bundle"
    source = _source(tmp_path / "source")
    _seed_bundle(bundle)

    code = main(["ingest", str(source), "--bundle", str(bundle), "--review", "--json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["committed"] is False
    assert payload["flags_acknowledged"] is True
    assert all(decision == "reject" for decision in payload["review"].values())


def test_review_dry_run_shows_the_plan_and_never_asks(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = tmp_path / "bundle"
    source = _source(tmp_path / "source")
    _seed_bundle(bundle)

    code = main(["ingest", str(source), "--bundle", str(bundle), "--review", "--dry-run"])

    assert code == 0
    assert "dry run: no changes written." in capsys.readouterr().out


def test_review_approves_some_items_interactively(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = tmp_path / "bundle"
    source = _source(tmp_path / "source")
    _seed_bundle(bundle)
    store = GitStore(bundle)

    # Simulate an interactive terminal answering "reject" to every prompt
    # except the one for the new concept file itself.
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    answers = iter(["n", "n", "y", "n"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))

    code = main(["ingest", str(source), "--bundle", str(bundle), "--review"])

    assert code == 0
    out = capsys.readouterr().out
    assert "committed" in out
    assert store.current_sha("HEAD") != store.current_sha("main")
    tracked = store.tracked_files(store.head_branch())
    assert "widget-policy.md" in tracked
    # index.md and log.md were rejected, so they stay off the committed branch.
    assert "log.md" not in tracked
