"""Permissive consumption: warnings (not errors) for the spec's tolerated cases.

OKF spec §7 — consumers MUST NOT reject a bundle for missing optional fields,
unknown ``type`` values, unknown extra keys, broken cross-links, or a missing
``index.md``. A broken cross-link is surfaced as a warning; the rest pass clean.
"""

from __future__ import annotations

from pathlib import Path

from kosha.validate import Rule, Severity, validate_bundle


def _bundle(root: Path, files: dict[str, str]) -> Path:
    for rel, content in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return root


def test_broken_link_is_a_warning_not_an_error(tmp_path: Path) -> None:
    root = _bundle(
        tmp_path,
        {
            "concepts/a.md": (
                "---\ntype: Metric\n---\n\n"
                "Depends on [missing](/concepts/not-written.md).\n"
            )
        },
    )
    report = validate_bundle(root)
    assert report.ok  # warnings never fail validation
    assert [f.rule for f in report.warnings] == [Rule.BROKEN_LINK]
    assert report.warnings[0].severity is Severity.WARNING
    assert report.errors == []


def test_valid_link_produces_no_warning(tmp_path: Path) -> None:
    root = _bundle(
        tmp_path,
        {
            "tables/orders.md": "---\ntype: Table\n---\n\nrows\n",
            "concepts/a.md": "---\ntype: Metric\n---\n\nSee [o](/tables/orders.md).\n",
        },
    )
    report = validate_bundle(root)
    assert report.ok
    assert report.findings == []


def test_unknown_type_value_is_permitted(tmp_path: Path) -> None:
    root = _bundle(tmp_path, {"a.md": "---\ntype: SomeNovelType\n---\n\nbody\n"})
    assert validate_bundle(root).ok


def test_missing_optional_fields_are_permitted(tmp_path: Path) -> None:
    # Only ``type`` is present; title/description/tags/timestamp all absent.
    root = _bundle(tmp_path, {"a.md": "---\ntype: Metric\n---\n\nbody\n"})
    assert validate_bundle(root).findings == []


def test_unknown_extra_keys_are_permitted(tmp_path: Path) -> None:
    root = _bundle(
        tmp_path,
        {"a.md": "---\ntype: Metric\nowner: data-team\nsla: gold\n---\n\nbody\n"},
    )
    assert validate_bundle(root).findings == []


def test_missing_index_is_permitted(tmp_path: Path) -> None:
    # A bundle with no index.md anywhere is still conformant.
    root = _bundle(tmp_path, {"tables/orders.md": "---\ntype: Table\n---\n\nrows\n"})
    assert validate_bundle(root).ok
