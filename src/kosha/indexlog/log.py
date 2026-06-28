"""Append dated entries to a ``log.md``, newest-first (OKF §6.6).

``log.md`` records a directory's change history as a flat list of date-grouped
entries under ISO ``YYYY-MM-DD`` headings, **newest first** — the audit trail of
the bundle's self-maintenance (system_design §2.2). Appending parses the existing
log, merges new entries into their date group, and re-renders every date in
descending order, so the newest-first invariant the M3 validator checks always
holds regardless of the order entries arrive in.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

LOG_TITLE = "# Update Log"
LOG_NAME = "log.md"

_DATE_HEADING = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s*$")


@dataclass(frozen=True)
class LogEntry:
    """One dated change line: ``* **<kind>**: <summary>`` under ``## <on>``."""

    on: date
    kind: str
    summary: str


def render_entry(entry: LogEntry) -> str:
    """Render a single log bullet (the leading bold kind is OKF §6.6 convention)."""
    return f"* **{entry.kind}**: {entry.summary}"


def append_entries(existing: str, entries: Sequence[LogEntry]) -> str:
    """Return ``existing`` with ``entries`` merged in, dates ordered newest-first."""
    title, groups = _parse_log(existing)
    for entry in entries:
        groups.setdefault(entry.on, []).append(render_entry(entry))
    return _render_log(title, groups)


def append_to_log(root: Path, entries: Sequence[LogEntry]) -> Path:
    """Append ``entries`` to ``<root>/log.md`` (creating it), return the path."""
    path = root / LOG_NAME
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    path.write_text(append_entries(existing, entries), encoding="utf-8")
    return path


def _parse_log(text: str) -> tuple[str, dict[date, list[str]]]:
    title = LOG_TITLE
    for line in text.splitlines():
        if line.startswith("# ") and not line.startswith("## "):
            title = line.rstrip()
            break
    groups: dict[date, list[str]] = {}
    current: list[str] | None = None
    for line in text.splitlines():
        stripped = line.strip()
        match = _DATE_HEADING.match(stripped)
        if match:
            current = groups.setdefault(date.fromisoformat(match.group(1)), [])
        elif stripped.startswith("#"):
            current = None
        elif current is not None and stripped:
            current.append(line.rstrip())
    return title, groups


def _render_log(title: str, groups: dict[date, list[str]]) -> str:
    blocks = [title]
    for on in sorted(groups, reverse=True):
        blocks.append("\n".join([f"## {on.isoformat()}", *groups[on]]))
    return "\n\n".join(blocks) + "\n"
