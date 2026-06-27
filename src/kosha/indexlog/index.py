"""Regenerate per-directory ``index.md`` files for progressive disclosure.

The index generator is deterministic (system_design §2.2 "Index/Log generator").
Each directory's ``index.md`` lists that directory's *direct* contents — immediate
subdirectories (linked through their own ``index.md``) and concept documents,
reusing each concept's ``description`` (OKF §6.5). Descending into a subdirectory's
index reveals the next level: an agent reads the map before opening documents.

Conformance guards (system_design §3, enforced by the M3 validator):

* ``index.md`` carries **no frontmatter** — the sole exception is the bundle-root
  index, which may declare ``okf_version``.
* Links are **bundle-relative standard Markdown**, never ``[[wikilinks]]`` — the
  shared :func:`~kosha.okf.serialize.serialize_index` writer enforces this.
"""

from __future__ import annotations

from pathlib import Path

from kosha.model import Bundle, IndexDoc, IndexEntry, IndexSection
from kosha.okf.serialize import serialize_index


def directory_of(concept_id: str) -> str:
    """Return a concept id's parent directory (``""`` for a root-level concept)."""
    parent, _, _ = concept_id.rpartition("/")
    return parent


def bundle_directories(bundle: Bundle) -> list[str]:
    """Return every directory that contains a concept, root first, sorted."""
    directories = {""}
    for concept_id in bundle.concepts:
        parts = concept_id.split("/")
        for depth in range(1, len(parts)):
            directories.add("/".join(parts[:depth]))
    return sorted(directories)


def regenerate_index(bundle: Bundle, directory: str) -> IndexDoc:
    """Build the :class:`~kosha.model.IndexDoc` for one directory.

    Entries are immediate subdirectories first (each linking its ``index.md``),
    then direct concept documents, both sorted for deterministic output. Only the
    bundle-root index (``directory == ""``) carries ``okf_version``.
    """
    prefix = f"{directory}/" if directory else ""
    subdirectories: set[str] = set()
    concept_ids: list[str] = []
    for concept_id in bundle.concepts:
        if not concept_id.startswith(prefix):
            continue
        rest = concept_id[len(prefix) :]
        head, slash, _ = rest.partition("/")
        if slash:
            subdirectories.add(prefix + head)
        else:
            concept_ids.append(concept_id)

    entries: list[IndexEntry] = [
        IndexEntry(title=_humanize(_basename(subdir)), target=f"{subdir}/index")
        for subdir in sorted(subdirectories)
    ]
    for concept_id in sorted(concept_ids):
        concept = bundle.concepts[concept_id]
        entries.append(
            IndexEntry(
                title=concept.frontmatter.title or _humanize(_basename(concept_id)),
                target=concept_id,
                description=concept.frontmatter.description,
            )
        )

    heading = _humanize(_basename(directory)) if directory else _root_heading(bundle)
    okf_version = bundle.okf_version if directory == "" else None
    section = IndexSection(heading=heading, entries=entries)
    return IndexDoc(sections=[section], okf_version=okf_version)


def regenerate_indexes(bundle: Bundle) -> dict[str, str]:
    """Map each directory's ``index.md`` bundle-relative path to its serialized text."""
    result: dict[str, str] = {}
    for directory in bundle_directories(bundle):
        rel = f"{directory}/index.md" if directory else "index.md"
        result[rel] = serialize_index(regenerate_index(bundle, directory))
    return result


def write_indexes(root: Path, bundle: Bundle) -> list[Path]:
    """Regenerate and write every directory's ``index.md`` under ``root``."""
    written: list[Path] = []
    for rel, content in regenerate_indexes(bundle).items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return written


def _basename(path: str) -> str:
    return path.rpartition("/")[2]


def _humanize(name: str) -> str:
    return name.replace("-", " ").replace("_", " ").title()


def _root_heading(bundle: Bundle) -> str:
    name = Path(bundle.root_path).name
    return _humanize(name) if name else "Index"
