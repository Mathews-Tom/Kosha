"""Serialize the typed model back to OKF markdown.

Serialization is deterministic and idempotent: a concept parsed from canonical
OKF markdown serializes back byte-for-byte. The index serializer can never emit a
``type:`` key and generated index links are absolute bundle-relative
(``/path/to/concept.md``), since those are the conformance properties conversion
tools commonly violate.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import yaml

from kosha.model import Concept, Frontmatter, IndexDoc

# Disable PyYAML's default line folding (best_width=80) so long frontmatter
# scalars (descriptions, titles, URLs) stay on one line and round-trip byte-stable.
_YAML_WIDTH = 2**31


class _FrontmatterDumper(yaml.SafeDumper):
    """YAML dumper that emits OKF-canonical scalars."""


def _represent_datetime(dumper: _FrontmatterDumper, value: datetime) -> yaml.Node:
    """Emit UTC datetimes with a ``Z`` suffix and others with an explicit offset.

    ``isoformat`` is used (not ``strftime``) so sub-second precision is preserved.
    """
    text = (
        value.isoformat().replace("+00:00", "Z")
        if value.tzinfo == UTC
        else value.isoformat()
    )
    return dumper.represent_scalar("tag:yaml.org,2002:timestamp", text)


def _represent_list(dumper: _FrontmatterDumper, value: list[Any]) -> yaml.Node:
    """Emit lists (e.g. ``tags``) in flow style: ``[a, b, c]``."""
    return dumper.represent_sequence("tag:yaml.org,2002:seq", value, flow_style=True)


_FrontmatterDumper.add_representer(datetime, _represent_datetime)
_FrontmatterDumper.add_representer(list, _represent_list)


def serialize_frontmatter(frontmatter: Frontmatter) -> str:
    """Render frontmatter to canonical YAML (no delimiters).

    Known fields keep schema order, then producer extensions in insertion order.
    ``None`` fields and empty lists are dropped so absent metadata is not emitted.
    """
    data = frontmatter.model_dump(mode="python", exclude_none=True)
    data = {key: value for key, value in data.items() if not _is_empty_list(value)}
    return yaml.dump(
        data,
        Dumper=_FrontmatterDumper,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=_YAML_WIDTH,
    )


def serialize_concept(concept: Concept) -> str:
    """Render a concept to OKF markdown: frontmatter block plus verbatim body."""
    return f"---\n{serialize_frontmatter(concept.frontmatter)}---\n{concept.body}"


def serialize_index(index: IndexDoc) -> str:
    """Render an ``index.md`` body with bundle-relative links and no ``type:``.

    Frontmatter is emitted only when ``okf_version`` is set (a bundle-root index).
    """
    blocks: list[str] = []
    for section in index.sections:
        lines = [f"# {section.heading}"]
        if section.entries:
            lines.append("")
            for entry in section.entries:
                link = f"[{entry.title}](/{entry.target}.md)"
                item = f"* {link} - {entry.description}" if entry.description else f"* {link}"
                lines.append(item)
        blocks.append("\n".join(lines))
    body = "\n\n".join(blocks)
    if body:
        body += "\n"
    if index.okf_version is None:
        return body
    front = yaml.dump(
        {"okf_version": index.okf_version},
        Dumper=_FrontmatterDumper,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=_YAML_WIDTH,
    )
    return f"---\n{front}---\n\n{body}"


def render_citations(citations: list[str]) -> str:
    """Render a numbered ``# Citations`` section, or ``""`` when there are none."""
    if not citations:
        return ""
    lines = ["# Citations"]
    lines.extend(f"[{number}] {citation}" for number, citation in enumerate(citations, start=1))
    return "\n".join(lines) + "\n"


def _is_empty_list(value: object) -> bool:
    return isinstance(value, list) and not value
