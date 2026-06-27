"""End-to-end CLI + fixture tests: good bundle exits 0, bad bundle exits non-zero."""

from __future__ import annotations

from pathlib import Path

import pytest

from kosha.cli import main
from kosha.validate import Rule, Severity, validate_bundle

_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
GOOD_BUNDLE = _FIXTURES / "good_bundle"
BAD_BUNDLE = _FIXTURES / "bad_bundle"


def test_good_bundle_exits_zero() -> None:
    assert main(["validate", str(GOOD_BUNDLE)]) == 0


def test_bad_bundle_exits_nonzero() -> None:
    assert main(["validate", str(BAD_BUNDLE)]) != 0


def test_good_bundle_is_conformant_with_a_broken_link_warning() -> None:
    report = validate_bundle(GOOD_BUNDLE)
    assert report.ok
    assert report.errors == []
    assert any(f.rule is Rule.BROKEN_LINK for f in report.warnings)


def test_bad_bundle_missing_type_is_a_type_error() -> None:
    report = validate_bundle(BAD_BUNDLE)
    assert any(
        f.rule is Rule.TYPE and f.path == "concepts/no-type.md" for f in report.errors
    )


def test_bad_bundle_covers_all_three_conformance_rules() -> None:
    report = validate_bundle(BAD_BUNDLE)
    rules = {f.rule for f in report.errors}
    assert {Rule.FRONTMATTER, Rule.TYPE, Rule.RESERVED_INDEX} <= rules
    assert all(f.severity is Severity.ERROR for f in report.errors)


def test_validate_nonexistent_path_exits_two() -> None:
    assert main(["validate", str(_FIXTURES / "does_not_exist")]) == 2


def test_cli_prints_findings(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate", str(BAD_BUNDLE)]) == 1
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert Rule.TYPE.value in out
