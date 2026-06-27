"""OKF v0.1 conformance rules: frontmatter, type, and reserved-file structure."""

from __future__ import annotations

from pathlib import Path

from kosha.validate import Rule, validate_bundle

_ORDERS = """---
type: BigQuery Table
title: Orders
---

# Schema

Order data.
"""


def _bundle(root: Path, files: dict[str, str]) -> Path:
    """Materialize ``files`` (rel path -> content) under ``root`` and return it."""
    for rel, content in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return root


def test_conformant_bundle_has_no_findings(tmp_path: Path) -> None:
    root = _bundle(
        tmp_path,
        {
            "index.md": "---\nokf_version: '0.1'\n---\n\n# Index\n",
            "tables/orders.md": _ORDERS,
            "log.md": "# Log\n\n## 2026-06-27\n* Update.\n\n## 2026-01-01\n* Creation.\n",
        },
    )
    report = validate_bundle(root)
    assert report.ok
    assert report.findings == []


def test_missing_type_is_a_type_finding(tmp_path: Path) -> None:
    root = _bundle(tmp_path, {"a.md": "---\ntitle: no type\n---\n\nbody\n"})
    report = validate_bundle(root)
    assert not report.ok
    assert [f.rule for f in report.findings] == [Rule.TYPE]
    assert report.findings[0].path == "a.md"


def test_empty_type_is_a_type_finding(tmp_path: Path) -> None:
    root = _bundle(tmp_path, {"a.md": "---\ntype: '   '\n---\n\nbody\n"})
    report = validate_bundle(root)
    assert [f.rule for f in report.findings] == [Rule.TYPE]


def test_missing_frontmatter_block_is_a_frontmatter_finding(tmp_path: Path) -> None:
    root = _bundle(tmp_path, {"a.md": "# Just a heading, no frontmatter\n"})
    report = validate_bundle(root)
    assert [f.rule for f in report.findings] == [Rule.FRONTMATTER]


def test_unparseable_frontmatter_is_a_frontmatter_finding(tmp_path: Path) -> None:
    root = _bundle(tmp_path, {"a.md": "---\ntype: : bad\n: nope\n---\nbody\n"})
    report = validate_bundle(root)
    assert [f.rule for f in report.findings] == [Rule.FRONTMATTER]


def test_non_mapping_frontmatter_is_a_frontmatter_finding(tmp_path: Path) -> None:
    root = _bundle(tmp_path, {"a.md": "---\n- just\n- a list\n---\nbody\n"})
    report = validate_bundle(root)
    assert [f.rule for f in report.findings] == [Rule.FRONTMATTER]


def test_non_root_index_must_not_have_frontmatter(tmp_path: Path) -> None:
    root = _bundle(
        tmp_path,
        {
            "index.md": "# Root index, no frontmatter\n",
            "tables/index.md": "---\nokf_version: '0.1'\n---\n\n# Tables\n",
        },
    )
    report = validate_bundle(root)
    assert [f.rule for f in report.findings] == [Rule.RESERVED_INDEX]
    assert report.findings[0].path == "tables/index.md"


def test_root_index_rejects_keys_other_than_okf_version(tmp_path: Path) -> None:
    root = _bundle(tmp_path, {"index.md": "---\ntype: Index\ntitle: Home\n---\n\n# Home\n"})
    report = validate_bundle(root)
    assert [f.rule for f in report.findings] == [Rule.RESERVED_INDEX]
    assert "type" in report.findings[0].message
    assert "title" in report.findings[0].message


def test_root_index_with_only_okf_version_is_conformant(tmp_path: Path) -> None:
    root = _bundle(tmp_path, {"index.md": "---\nokf_version: '0.1'\n---\n\n# Home\n"})
    assert validate_bundle(root).ok


def test_reserved_files_are_exempt_from_frontmatter_and_type_rules(tmp_path: Path) -> None:
    # index.md and log.md carry no ``type`` and (here) no frontmatter; that is
    # conformant — rules 1 and 2 apply only to non-reserved files.
    root = _bundle(
        tmp_path,
        {"index.md": "# Home\n", "tables/index.md": "# Tables\n", "log.md": "# Log\n"},
    )
    assert validate_bundle(root).ok


def test_log_dates_must_be_newest_first(tmp_path: Path) -> None:
    root = _bundle(
        tmp_path,
        {"log.md": "# Log\n\n## 2026-01-01\n* Old.\n\n## 2026-06-27\n* New.\n"},
    )
    report = validate_bundle(root)
    assert [f.rule for f in report.findings] == [Rule.RESERVED_LOG]
    assert "newest-first" in report.findings[0].message


def test_log_date_headings_must_be_valid_iso(tmp_path: Path) -> None:
    root = _bundle(tmp_path, {"log.md": "# Log\n\n## 2026-13-45\n* Bad date.\n"})
    report = validate_bundle(root)
    assert [f.rule for f in report.findings] == [Rule.RESERVED_LOG]
    assert "valid ISO date" in report.findings[0].message


def test_findings_are_ordered_by_path(tmp_path: Path) -> None:
    root = _bundle(
        tmp_path,
        {
            "b/concept.md": "# no frontmatter\n",
            "a/concept.md": "---\ntitle: no type\n---\nbody\n",
        },
    )
    report = validate_bundle(root)
    assert [f.path for f in report.findings] == ["a/concept.md", "b/concept.md"]
    assert [f.rule for f in report.findings] == [Rule.TYPE, Rule.FRONTMATTER]
