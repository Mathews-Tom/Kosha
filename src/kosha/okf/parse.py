"""Parse OKF concept documents into the typed model.

Parsing is loss-tolerant: the body is kept verbatim and unknown frontmatter keys
are preserved (see :class:`kosha.model.Frontmatter`), so a parse/serialize cycle
is byte-stable for canonically formatted documents. Permissive consumption is the
spec's rule — the parser does not reject documents for missing optional fields,
unknown types, extra keys, or broken links; only a missing/unparseable
frontmatter block is a hard error.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any

import yaml
from pydantic import ValidationError

from kosha.model import Concept, Frontmatter
from kosha.okf.errors import FrontmatterError

# Frontmatter block: opening ``---`` line, YAML up to a closing ``---`` line,
# then the body. ``fm`` keeps its trailing newline and ``body`` keeps its leading
# newline so the serializer reconstructs the document byte-for-byte.
_FRONTMATTER = re.compile(
    r"\A---\n(?P<fm>.*?\n)---[^\S\n]*(?:\n(?P<body>.*))?\Z",
    re.DOTALL,
)

# Inline markdown link: ``[text](target)``. Targets are filtered to in-bundle
# ``.md`` paths in :func:`_extract_out_links`.
_MD_LINK = re.compile(r"\[[^\]]*\]\((?P<target>[^)]+)\)")


def concept_id_from_path(rel_path: str) -> str:
    """Return the concept id for a bundle-relative path: the path minus ``.md``.

    Identity is the path, so ``tables/orders.md`` is concept id ``tables/orders``.
    Backslashes are normalized to POSIX separators.
    """
    pure = PurePosixPath(rel_path.replace("\\", "/"))
    if pure.suffix != ".md":
        raise ValueError(f"concept path must end in '.md': {rel_path!r}")
    return pure.with_suffix("").as_posix()


def load_raw_frontmatter(text: str) -> tuple[dict[str, Any] | None, str]:
    """Split a document into its raw frontmatter mapping and verbatim body.

    Returns ``(None, text)`` when no ``---`` frontmatter block is present, and
    ``(mapping, body)`` when one is — where ``mapping`` is the untyped YAML
    mapping (``{}`` for an empty block). Raises :class:`FrontmatterError` only
    when a block is present but its YAML is unparseable or is not a mapping.

    This is the low-level splitter the conformance validator uses to tell a
    missing frontmatter block (rule 1) apart from a present block missing a
    ``type`` (rule 2); :func:`parse_frontmatter` layers typed validation on top.
    """
    match = _FRONTMATTER.match(text)
    if match is None:
        return None, text
    try:
        raw = yaml.safe_load(match.group("fm"))
    except yaml.YAMLError as exc:
        raise FrontmatterError(f"frontmatter is not valid YAML: {exc}") from exc
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise FrontmatterError("frontmatter must be a YAML mapping")
    return raw, match.group("body") or ""


def parse_frontmatter(text: str) -> tuple[Frontmatter, str]:
    """Split a concept document into typed frontmatter and a verbatim body."""
    mapping, body = load_raw_frontmatter(text)
    if mapping is None:
        raise FrontmatterError("document has no parseable frontmatter block")
    try:
        frontmatter = Frontmatter(**mapping)
    except ValidationError as exc:
        raise FrontmatterError(f"frontmatter failed validation: {exc}") from exc
    return frontmatter, body


def parse_concept(rel_path: str, text: str) -> Concept:
    """Parse a concept document at ``rel_path`` into a :class:`Concept`."""
    concept_id = concept_id_from_path(rel_path)
    frontmatter, body = parse_frontmatter(text)
    out_links = _extract_out_links(concept_id, body)
    return Concept(
        concept_id=concept_id,
        frontmatter=frontmatter,
        body=body,
        out_links=out_links,
    )


def _extract_out_links(concept_id: str, body: str) -> list[str]:
    """Collect in-bundle concept ids the body links to, in first-seen order.

    Bundle-relative (``/a/b.md``) and relative (``./b.md``, ``../c.md``) markdown
    links to ``.md`` targets are resolved to concept ids; external URLs, anchors,
    non-``.md`` targets, and links that climb above the bundle root are ignored.
    """
    base = PurePosixPath(concept_id).parent
    out_links: list[str] = []
    for match in _MD_LINK.finditer(body):
        target = match.group("target").strip().split("#", 1)[0]
        if not target or "://" in target or target.startswith("mailto:"):
            continue
        if not target.endswith(".md"):
            continue
        resolved = (
            PurePosixPath(target.lstrip("/"))
            if target.startswith("/")
            else base / target
        )
        cid = _normalize(resolved.with_suffix(""))
        if cid and cid not in out_links:
            out_links.append(cid)
    return out_links


def _normalize(path: PurePosixPath) -> str | None:
    """Collapse ``.``/``..`` into a concept id, or ``None`` if it escapes the root."""
    parts: list[str] = []
    for part in path.parts:
        if part == "..":
            if not parts:
                return None
            parts.pop()
        elif part not in ("", "."):
            parts.append(part)
    return "/".join(parts)
