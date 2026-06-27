"""Load an on-disk OKF bundle directory into the typed :class:`Bundle` model.

The loader is the read path the maintenance loop and the consumer surface share:
it walks a bundle directory, parses every concept document into a
:class:`~kosha.model.Concept` (keyed by ``concept_id``), and records each
concept's out-links. Reserved files (``index.md``/``log.md``) are structure, not
concepts, so they are skipped here; their conventions are enforced by the
validator, not this loader.
"""

from __future__ import annotations

from pathlib import Path

from kosha.model import Bundle, Concept
from kosha.okf.parse import parse_concept

# Reserved basenames that are bundle structure rather than concept documents.
_RESERVED = frozenset({"index.md", "log.md"})


def load_bundle(root: Path, *, okf_version: str = "0.1") -> Bundle:
    """Parse every concept document under ``root`` into a :class:`Bundle`.

    ``index.md`` and ``log.md`` files are skipped. Concepts are keyed by
    ``concept_id`` (the bundle-relative path minus ``.md``). Files are visited in
    sorted path order so the resulting mapping is deterministic.
    """
    if not root.is_dir():
        raise NotADirectoryError(f"not a bundle directory: {root}")
    concepts: dict[str, Concept] = {}
    for path in sorted(root.rglob("*.md")):
        if path.name in _RESERVED:
            continue
        rel = path.relative_to(root).as_posix()
        concept = parse_concept(rel, path.read_text(encoding="utf-8"))
        concepts[concept.concept_id] = concept
    return Bundle(root_path=str(root), okf_version=okf_version, concepts=concepts)
