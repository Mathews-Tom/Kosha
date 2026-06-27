"""Smoke tests: the package imports, exposes a semver, and the CLI runs."""

from __future__ import annotations

import re

import pytest

import kosha
from kosha.cli import main

_SEMVER = re.compile(r"\d+\.\d+\.\d+")


def test_version_is_semver() -> None:
    assert _SEMVER.search(kosha.__version__) is not None


def test_cli_help_exits_clean(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "usage: kosha" in capsys.readouterr().out


def test_cli_version_prints_semver(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0
    assert _SEMVER.search(capsys.readouterr().out) is not None
