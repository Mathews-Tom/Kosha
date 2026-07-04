"""``kosha ingest --dry-run --review-queue``: dry-run never persists a queue.

A dry run only builds and prints the plan; it must not have any side effect
on the shared review-queue file, including creating it.
"""

from __future__ import annotations

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


def test_dry_run_ingest_with_review_queue_never_writes_a_queue_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = tmp_path / "bundle"
    source = _source(tmp_path / "source")
    _seed_bundle(bundle)
    queue_path = tmp_path / "queue.json"

    code = main(
        [
            "ingest",
            str(source),
            "--bundle",
            str(bundle),
            "--dry-run",
            "--review-queue",
            str(queue_path),
        ]
    )

    assert code == 0
    assert "dry run: no changes written. review queue not written." in capsys.readouterr().out
    assert not queue_path.exists()


def test_review_queue_with_no_subcommand_exits_two_instead_of_an_attribute_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # ``args.queue_command`` is None until a "list"/"decide" subcommand is
    # chosen, and only those subparsers define the ``queue`` positional --
    # dispatching straight through to it without checking first used to raise
    # an uncaught AttributeError instead of a clean CLI usage error.
    code = main(["review-queue"])

    assert code == 2
    assert "review-queue requires a subcommand" in capsys.readouterr().err
