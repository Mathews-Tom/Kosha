"""OKF v0.1 conformance validation over a bundle directory.

The validator walks a bundle's ``.md`` files and applies the three OKF v0.1
conformance rules (OKF spec §7):

1. Every *non-reserved* ``.md`` file contains a parseable YAML frontmatter block.
2. Every frontmatter block has a non-empty ``type`` field.
3. Reserved files (``index.md``, ``log.md``) follow their structural conventions
   when present — index files carry no frontmatter (except a bundle-root
   ``index.md`` declaring only ``okf_version``); log files use ISO
   ``YYYY-MM-DD`` date headings ordered newest-first.

Conformance violations are hard failures. Permissive-consumption concerns
(broken cross-links, granularity) are layered on top by the warning model.
"""

from __future__ import annotations

import re
from datetime import date
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

from kosha.okf.errors import FrontmatterError
from kosha.okf.parse import load_raw_frontmatter

# Reserved file basenames whose structure is governed by rule 3 and which are
# exempt from the frontmatter rules (1 and 2).
RESERVED_NAMES = ("index.md", "log.md")

# A ``log.md`` date heading: a level-2 heading whose text is an ISO date.
_LOG_DATE_HEADING = re.compile(r"(?m)^##[ \t]+(\d{4}-\d{2}-\d{2})[ \t]*$")


class Rule(StrEnum):
    """Identifier for a conformance rule, surfaced in findings and tests."""

    FRONTMATTER = "okf-frontmatter"  # rule 1: parseable frontmatter block
    TYPE = "okf-type"  # rule 2: non-empty ``type``
    RESERVED_INDEX = "okf-reserved-index"  # rule 3: ``index.md`` convention
    RESERVED_LOG = "okf-reserved-log"  # rule 3: ``log.md`` convention


class Finding(BaseModel):
    """A single conformance issue found in a bundle file."""

    rule: Rule
    path: str
    message: str


class Report(BaseModel):
    """The outcome of validating a bundle."""

    findings: list[Finding] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when the bundle is conformant (no findings)."""
        return not self.findings


def validate_bundle(root: Path) -> Report:
    """Validate every ``.md`` file under ``root`` against OKF v0.1 conformance.

    Files are visited in sorted path order so findings are deterministic.
    """
    findings: list[Finding] = []
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        if path.name == "index.md":
            findings.extend(_check_index(rel, text, is_root=path.parent == root))
        elif path.name == "log.md":
            findings.extend(_check_log(rel, text))
        else:
            findings.extend(_check_concept(rel, text))
    return Report(findings=findings)


def _check_concept(rel: str, text: str) -> list[Finding]:
    """Apply rules 1 (parseable frontmatter) and 2 (non-empty ``type``)."""
    try:
        mapping, _ = load_raw_frontmatter(text)
    except FrontmatterError as exc:
        return [Finding(rule=Rule.FRONTMATTER, path=rel, message=str(exc))]
    if mapping is None:
        return [
            Finding(
                rule=Rule.FRONTMATTER,
                path=rel,
                message="file has no YAML frontmatter block",
            )
        ]
    type_value = mapping.get("type")
    if type_value is None:
        return [
            Finding(
                rule=Rule.TYPE,
                path=rel,
                message="frontmatter is missing a 'type' field",
            )
        ]
    if not str(type_value).strip():
        return [
            Finding(rule=Rule.TYPE, path=rel, message="frontmatter 'type' is empty")
        ]
    return []


def _check_index(rel: str, text: str, *, is_root: bool) -> list[Finding]:
    """Apply rule 3 to ``index.md``: no frontmatter, save a root ``okf_version``."""
    try:
        mapping, _ = load_raw_frontmatter(text)
    except FrontmatterError as exc:
        return [
            Finding(
                rule=Rule.RESERVED_INDEX,
                path=rel,
                message=f"index frontmatter is unparseable: {exc}",
            )
        ]
    if mapping is None:
        return []
    if not is_root:
        return [
            Finding(
                rule=Rule.RESERVED_INDEX,
                path=rel,
                message="non-root index.md must not contain frontmatter",
            )
        ]
    extra = sorted(key for key in mapping if key != "okf_version")
    if extra:
        return [
            Finding(
                rule=Rule.RESERVED_INDEX,
                path=rel,
                message=(
                    "root index.md frontmatter may only declare okf_version; "
                    f"found: {', '.join(extra)}"
                ),
            )
        ]
    return []


def _check_log(rel: str, text: str) -> list[Finding]:
    """Apply rule 3 to ``log.md``: ISO date headings ordered newest-first."""
    findings: list[Finding] = []
    parsed: list[date] = []
    headings: list[str] = _LOG_DATE_HEADING.findall(text)
    for raw in headings:
        try:
            parsed.append(date.fromisoformat(raw))
        except ValueError:
            findings.append(
                Finding(
                    rule=Rule.RESERVED_LOG,
                    path=rel,
                    message=f"log heading '{raw}' is not a valid ISO date",
                )
            )
    if parsed != sorted(parsed, reverse=True):
        findings.append(
            Finding(
                rule=Rule.RESERVED_LOG,
                path=rel,
                message="log date headings must be ordered newest-first",
            )
        )
    return findings
