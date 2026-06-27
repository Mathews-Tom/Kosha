"""Granularity lint: advisory one-concept-one-thing warnings, never errors."""

from __future__ import annotations

from pathlib import Path

from kosha.lint import MAX_BODY_WORDS, MAX_TOP_SECTIONS, granularity_warnings
from kosha.validate import Rule, validate_bundle


def test_granularity_flags_oversized_body() -> None:
    body = " ".join(["word"] * (MAX_BODY_WORDS + 1))
    messages = granularity_warnings(body)
    assert any("words" in m for m in messages)


def test_granularity_flags_too_many_sections() -> None:
    body = "\n\n".join(f"# Section {i}\n\ntext" for i in range(MAX_TOP_SECTIONS + 1))
    messages = granularity_warnings(body)
    assert any("top-level sections" in m for m in messages)


def test_granularity_ignores_deeper_headings() -> None:
    # ``## `` subsections must not count toward the top-level-section heuristic.
    body = "# One\n\n" + "\n\n".join(f"## Sub {i}" for i in range(MAX_TOP_SECTIONS + 5))
    assert granularity_warnings(body) == []


def test_small_concept_has_no_granularity_warnings() -> None:
    assert granularity_warnings("# Definition\n\nA short, focused concept.\n") == []


def _bundle(root: Path, files: dict[str, str]) -> Path:
    for rel, content in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return root


def test_validator_emits_granularity_warning_without_failing(tmp_path: Path) -> None:
    big_body = " ".join(["word"] * (MAX_BODY_WORDS + 1))
    root = _bundle(tmp_path, {"a.md": f"---\ntype: Metric\n---\n\n{big_body}\n"})
    report = validate_bundle(root)
    assert report.ok  # lint warnings never fail validation
    assert [f.rule for f in report.warnings] == [Rule.GRANULARITY]
