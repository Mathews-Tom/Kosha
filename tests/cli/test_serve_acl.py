"""``kosha serve``: fail-closed access-control and network-exposure gates.

Complements ``tests/mcp/test_registry.py`` (the ``build_bundles_dir_registry``
contract itself) with the CLI-layer checks that run before a registry is ever
built: a single-bundle ``--bundle-access`` targeting the wrong bundle id, an
unlabeled ``--bundles-dir`` child served without explicit opt-in, and binding
outside loopback without explicit opt-in. Every case here must refuse to
start rather than silently serving something broader than requested.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kosha.cli import main


def test_serve_refuses_a_non_loopback_host_without_allow_non_loopback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(["serve", "--host", "0.0.0.0", "--once"])

    assert code == 2
    assert "--allow-non-loopback" in capsys.readouterr().err


def test_serve_bundles_dir_refuses_an_unlabeled_child_without_allow_open_bundles(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundles_dir = tmp_path / "bundles"
    (bundles_dir / "alpha").mkdir(parents=True)

    code = main(["serve", "--bundles-dir", str(bundles_dir), "--once"])

    assert code == 2
    assert "alpha" in capsys.readouterr().err


def test_serve_single_bundle_access_targeting_a_different_bundle_id_fails_closed(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "serve",
                "--bundle",
                str(bundle),
                "--bundle-id",
                "mine",
                "--bundle-access",
                "other=confidential",
            ]
        )

    message = str(exc_info.value)
    assert "'other'" in message
    assert "'mine'" in message


def test_serve_single_bundle_blank_bare_access_fails_closed_instead_of_clearing_env_acl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A bare (no ``bundle_id=``) ``--bundle-access`` entry that strips to blank
    # must reject outright. Before this fix it silently became the configured
    # label, clearing whatever KOSHA_BUNDLE_ACCESS the environment set and
    # serving the bundle open to anyone with no clearance at all.
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    monkeypatch.setenv("KOSHA_BUNDLE_ACCESS", "confidential")

    with pytest.raises(SystemExit) as exc_info:
        main(["serve", "--bundle", str(bundle), "--bundle-access", "   "])

    assert "must not be blank" in str(exc_info.value)


def test_serve_bundles_dir_duplicate_bundle_access_ids_fail_closed(
    tmp_path: Path,
) -> None:
    bundles_dir = tmp_path / "bundles"
    (bundles_dir / "alpha").mkdir(parents=True)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "serve",
                "--bundles-dir",
                str(bundles_dir),
                "--bundle-access",
                "alpha=confidential",
                "--bundle-access",
                "alpha=public",
            ]
        )

    message = str(exc_info.value)
    assert "duplicate" in message
    assert "'alpha'" in message


def test_serve_bundles_dir_registry_value_error_exits_two_with_a_kosha_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # ``--bundle-access`` naming a bundle id that does not exist as a child
    # directory reaches ``build_bundles_dir_registry`` and raises there (not a
    # CLI-level parse error): the CLI must still fail closed with exit code 2
    # and a "kosha: " prefixed message, not an uncaught traceback.
    bundles_dir = tmp_path / "bundles"
    (bundles_dir / "alpha").mkdir(parents=True)

    code = main(
        [
            "serve",
            "--bundles-dir",
            str(bundles_dir),
            "--bundle-access",
            "alpha=confidential",
            "--bundle-access",
            "ghost=confidential",
            "--once",
        ]
    )

    assert code == 2
    err = capsys.readouterr().err
    assert err.startswith("kosha: ")
    assert "ghost" in err
