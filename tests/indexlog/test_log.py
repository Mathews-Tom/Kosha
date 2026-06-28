"""Newest-first dated log.md append (M8 PR-4)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from kosha.indexlog import LogEntry, append_entries, append_to_log, render_entry
from kosha.validate import Rule, validate_bundle


def _entry(on: tuple[int, int, int], kind: str, summary: str) -> LogEntry:
    return LogEntry(on=date(*on), kind=kind, summary=summary)


def test_render_entry_uses_bold_kind_convention() -> None:
    entry = _entry((2026, 6, 27), "Creation", "Established [Refunds](/policies/refunds.md).")
    assert render_entry(entry) == "* **Creation**: Established [Refunds](/policies/refunds.md)."


def test_append_to_empty_log_writes_title_and_dated_entry() -> None:
    out = append_entries("", [_entry((2026, 6, 27), "Update", "Linked returns to refunds.")])
    assert out == (
        "# Update Log\n\n## 2026-06-27\n* **Update**: Linked returns to refunds.\n"
    )


def test_entries_are_ordered_newest_first_regardless_of_arrival_order() -> None:
    out = append_entries(
        "",
        [
            _entry((2026, 1, 1), "Creation", "Seeded the bundle."),
            _entry((2026, 6, 27), "Update", "Cross-linked policies."),
            _entry((2026, 3, 15), "Update", "Added entities."),
        ],
    )
    headings = [line for line in out.splitlines() if line.startswith("## ")]
    assert headings == ["## 2026-06-27", "## 2026-03-15", "## 2026-01-01"]


def test_same_date_entries_group_under_one_heading() -> None:
    out = append_entries(
        "",
        [
            _entry((2026, 6, 27), "Creation", "Minted membership-tier."),
            _entry((2026, 6, 27), "Update", "Linked customer to order."),
        ],
    )
    assert out.count("## 2026-06-27") == 1
    assert "* **Creation**: Minted membership-tier." in out
    assert "* **Update**: Linked customer to order." in out


def test_append_preserves_existing_entries_and_orders_new_date() -> None:
    existing = "# Update Log\n\n## 2026-06-10\n* **Creation**: Added playbooks.\n"
    out = append_entries(existing, [_entry((2026, 6, 27), "Update", "Regenerated indexes.")])
    headings = [line for line in out.splitlines() if line.startswith("## ")]
    assert headings == ["## 2026-06-27", "## 2026-06-10"]
    assert "* **Creation**: Added playbooks." in out


def test_append_to_an_existing_date_keeps_prior_bullets() -> None:
    existing = "# Update Log\n\n## 2026-06-27\n* **Creation**: First change.\n"
    out = append_entries(existing, [_entry((2026, 6, 27), "Update", "Second change.")])
    assert out.count("## 2026-06-27") == 1
    assert "* **Creation**: First change." in out
    assert "* **Update**: Second change." in out


def test_append_to_log_writes_conformant_log(tmp_path: Path) -> None:
    (tmp_path / "note.md").write_text("---\ntype: Concept\n---\n\n# Note\n", encoding="utf-8")
    path = append_to_log(
        tmp_path,
        [
            _entry((2026, 1, 1), "Creation", "Seeded."),
            _entry((2026, 6, 27), "Update", "Linked."),
        ],
    )
    assert path == tmp_path / "log.md"
    report = validate_bundle(tmp_path)
    assert report.ok
    # No reserved-log finding: ISO date headings, newest-first.
    assert all(finding.rule is not Rule.RESERVED_LOG for finding in report.findings)


def test_append_to_log_appends_across_calls(tmp_path: Path) -> None:
    append_to_log(tmp_path, [_entry((2026, 6, 10), "Creation", "First.")])
    append_to_log(tmp_path, [_entry((2026, 6, 27), "Update", "Second.")])
    text = (tmp_path / "log.md").read_text(encoding="utf-8")
    headings = [line for line in text.splitlines() if line.startswith("## ")]
    assert headings == ["## 2026-06-27", "## 2026-06-10"]
