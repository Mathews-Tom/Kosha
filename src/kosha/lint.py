"""Granularity lint: advisory "one concept, one thing" heuristics.

These checks are warnings only — they never fail conformance (system_design
§7.1: granularity is a lint, not a gate). They flag a concept document that
looks like it bundles several distinct concepts and should be split, which is
the same one-concept-one-thing rule the dedup ``split`` branch enforces later.
"""

from __future__ import annotations

import re

# A concept body longer than this many words probably bundles multiple concepts.
MAX_BODY_WORDS = 500
# More top-level ("# ") sections than this likewise suggests an over-scoped concept.
MAX_TOP_SECTIONS = 8

# A level-1 heading: a single "#" followed by whitespace then content. Deeper
# headings ("## ") have a second "#" immediately after the first and never match.
_TOP_SECTION = re.compile(r"(?m)^#[ \t]+\S")


def granularity_warnings(body: str) -> list[str]:
    """Return advisory granularity messages for a concept body (possibly empty)."""
    messages: list[str] = []
    word_count = len(body.split())
    if word_count > MAX_BODY_WORDS:
        messages.append(
            f"concept body is large ({word_count} words); "
            "consider splitting (one concept, one thing)"
        )
    section_count = len(_TOP_SECTION.findall(body))
    if section_count > MAX_TOP_SECTIONS:
        messages.append(
            f"concept has {section_count} top-level sections; "
            "consider splitting (one concept, one thing)"
        )
    return messages
