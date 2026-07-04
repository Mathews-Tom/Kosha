"""``kosha ingest --watch``: the CLI source arg reaches the URL policy gate as
the literal string, not a mangled ``Path`` (M9 served-team-mode review fix).

Before this fix, the ``ingest`` subcommand typed its ``source`` positional as
``Path``, so a URL handed to ``--watch`` was coerced into a local path before
``ScheduledIngest`` ever saw it: a denied host never reached the allowlist
gate, instead failing (or worse, silently "succeeding") as a bogus local
directory lookup. These tests exercise the parser -> dispatch wiring itself,
complementing the ``ScheduledIngest``-level unit tests in
``tests/ingest/test_watch.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kosha.cli import main
from kosha.git_store import GitStore
from kosha.model import RawDoc, Source, SourceKind


def _seed_bundle(root: Path) -> Path:
    store = GitStore.init(root)
    (root / "index.md").write_text('okf_version: "0.1"\n', encoding="utf-8")
    store.commit(["index.md"], "chore: seed")
    return root


def test_watch_ingest_passes_the_literal_url_string_to_the_source_policy_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _seed_bundle(tmp_path / "bundle")
    seen_urls: list[str] = []

    def _fake_fetch(url: str, **_kwargs: object) -> RawDoc:
        seen_urls.append(url)
        return RawDoc(
            source=Source(source_id="watch-fetch.md", kind=SourceKind.URL, location=url),
            text="# Shipping\n\nOrders ship within one business day of confirmation.\n",
        )

    monkeypatch.setattr("kosha.ingest.watch.fetch_url", _fake_fetch)

    code = main(
        [
            "ingest",
            "https://trusted.example/page",
            "--bundle",
            str(bundle),
            "--watch",
            "--allowed-host",
            "trusted.example",
            "--dry-run",
        ]
    )

    assert code == 0
    # The exact URL string reached fetch_url unchanged -- proof the CLI never
    # coerced it into a Path first.
    assert seen_urls == ["https://trusted.example/page"]


def test_watch_ingest_denied_host_fails_at_the_policy_gate_before_any_local_path_check(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = _seed_bundle(tmp_path / "bundle")

    # If the CLI still coerced ``source`` to a Path, this would instead exit 2
    # with "not a source directory" -- a URL never has a local directory to
    # check, so reaching the real UrlIngestError (converted to a code-2 exit
    # by the run_once() failure gate below) proves no such fallback ran.
    code = main(
        [
            "ingest",
            "https://denied.example/page",
            "--bundle",
            str(bundle),
            "--watch",
            "--allowed-host",
            "trusted.example",
            "--yes",
        ]
    )

    assert code == 2
    assert (
        "kosha: scheduled ingest failed: hostname 'denied.example' is not in the "
        "scheduled source allowlist" in capsys.readouterr().err
    )


def test_watch_ingest_run_once_value_error_exits_two_with_the_scheduled_ingest_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # A ValueError surfaced from inside run_once() (here: normalize_reviewer()
    # rejecting a newline-bearing --reviewer, a bug class distinct from the
    # UrlIngestError policy gate above) must fail the same way: code 2 and a
    # "kosha: scheduled ingest failed: ..." message, never an uncaught
    # traceback out of the scheduled-run loop.
    bundle = _seed_bundle(tmp_path / "bundle")

    def _fake_fetch(url: str, **_kwargs: object) -> RawDoc:
        return RawDoc(
            source=Source(source_id="watch-fetch.md", kind=SourceKind.URL, location=url),
            text="# Shipping\n\nOrders ship within one business day of confirmation.\n",
        )

    monkeypatch.setattr("kosha.ingest.watch.fetch_url", _fake_fetch)

    code = main(
        [
            "ingest",
            "https://trusted.example/page",
            "--bundle",
            str(bundle),
            "--watch",
            "--allowed-host",
            "trusted.example",
            "--yes",
            "--reviewer",
            "line one\nline two",
        ]
    )

    assert code == 2
    assert (
        "kosha: scheduled ingest failed: reviewer identity must not contain newlines"
        in capsys.readouterr().err
    )


def test_non_watch_ingest_still_requires_an_existing_local_source_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = _seed_bundle(tmp_path / "bundle")

    code = main(["ingest", str(tmp_path / "does-not-exist"), "--bundle", str(bundle)])

    assert code == 2
    assert "not a source directory" in capsys.readouterr().err


def test_watch_ingest_rejects_a_negative_runs_count(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        [
            "ingest",
            "https://trusted.example/page",
            "--bundle",
            str(tmp_path / "bundle"),
            "--watch",
            "--runs",
            "-1",
        ]
    )

    assert code == 2
    assert "--runs must be 0 or greater" in capsys.readouterr().err


def test_watch_ingest_rejects_a_zero_interval_seconds(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        [
            "ingest",
            "https://trusted.example/page",
            "--bundle",
            str(tmp_path / "bundle"),
            "--watch",
            "--interval-seconds",
            "0",
        ]
    )

    assert code == 2
    assert "--interval-seconds must be greater than 0" in capsys.readouterr().err
