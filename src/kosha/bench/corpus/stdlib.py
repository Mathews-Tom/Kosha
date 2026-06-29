"""Render the CPython standard library's docstrings into an OKF bundle.

M13 (DEVELOPMENT_PLAN §7) requires an external, not-Kosha-authored corpus of
500-2,000 concepts to benchmark the maintenance loop against tuned RAG and a
prompt-only baseline. The CPython standard library is the most reproducible such
source available offline: every public function/class/method carries a
PSF-licensed docstring, and the rendering is a pure function of the running
interpreter (pinned to 3.12 by ``.python-version``).

The rendering is deterministic — modules are walked in a fixed sorted order, a
fixed cap of members is taken per module in sorted name order, and only members
with a substantial docstring are emitted — so the committed bundle reproduces on
any machine with the same CPython. The committed ``bundles/pydoc-stdlib/`` bundle
is the benchmark's source of truth; this module is provenance and regeneration.
"""

from __future__ import annotations

import importlib
import inspect
import json
from dataclasses import dataclass
from pathlib import Path

CORPUS_NAME = "pydoc-stdlib"
SOURCE = "CPython standard library"
SOURCE_LICENSE = "Python Software Foundation License v2"

# A docstring must be at least this long to become a concept: short ones carry no
# retrievable knowledge and would only inflate the count.
MIN_DOC_CHARS = 80
# Cap members per module so no single module dominates the corpus; members are
# taken in sorted name order, so the cut is deterministic.
MAX_MEMBERS_PER_MODULE = 16
# How many sibling concepts each concept links to, so the hybrid strategy has
# out-links to traverse and the bundle is not a flat list of islands.
LINKS_PER_CONCEPT = 3
# Description is the first docstring line, collapsed and capped at this length.
MAX_DESCRIPTION_CHARS = 200
# Members whose name renders to a reserved bundle file are skipped (see _member_row).
_RESERVED_STEMS = frozenset({"index", "log"})

# Curated, import-safe, docstring-rich standard-library modules, walked in this
# fixed order. Chosen for breadth across the stdlib's documented surfaces; the
# list is the only intentional editorial input — member selection below is
# mechanical.
MODULES: tuple[str, ...] = (
    "argparse",
    "array",
    "ast",
    "base64",
    "bisect",
    "calendar",
    "cmath",
    "collections",
    "configparser",
    "contextlib",
    "copy",
    "csv",
    "datetime",
    "decimal",
    "difflib",
    "fnmatch",
    "fractions",
    "functools",
    "gzip",
    "hashlib",
    "heapq",
    "html",
    "http",
    "io",
    "ipaddress",
    "itertools",
    "json",
    "logging",
    "math",
    "mimetypes",
    "operator",
    "os",
    "pathlib",
    "pickle",
    "pprint",
    "queue",
    "random",
    "re",
    "secrets",
    "shlex",
    "shutil",
    "socket",
    "statistics",
    "string",
    "struct",
    "tempfile",
    "textwrap",
    "time",
    "tokenize",
    "typing",
    "unicodedata",
    "urllib.parse",
    "uuid",
    "zipfile",
    "zlib",
)


@dataclass(frozen=True)
class CorpusEntry:
    """One concept rendered from a stdlib member."""

    concept_id: str
    title: str
    description: str
    body: str
    tags: tuple[str, ...]
    out_links: tuple[str, ...]


@dataclass(frozen=True)
class CorpusStats:
    """What :func:`build_corpus` wrote."""

    concept_count: int
    module_count: int


def collect_entries(modules: tuple[str, ...] = MODULES) -> list[CorpusEntry]:
    """Render every selected stdlib member into a :class:`CorpusEntry` (sorted)."""
    entries: list[CorpusEntry] = []
    for module_name in modules:
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        entries.extend(_module_entries(module_name, module))
    return entries


def build_corpus(out_dir: Path, *, modules: tuple[str, ...] = MODULES) -> CorpusStats:
    """Write the rendered corpus as a conformant OKF bundle under ``out_dir``."""
    entries = collect_entries(modules)
    out_dir.mkdir(parents=True, exist_ok=True)
    module_dirs: set[str] = set()
    for entry in entries:
        path = out_dir / f"{entry.concept_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_render_concept(entry), encoding="utf-8")
    by_module = _group_by_module(entries)
    for module_name, module_entries in by_module.items():
        module_dirs.add(module_name)
        index_path = out_dir / module_name.replace(".", "/") / "index.md"
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(_render_module_index(module_name, module_entries), encoding="utf-8")
    (out_dir / "index.md").write_text(
        _render_root_index(by_module, len(entries)), encoding="utf-8"
    )
    (out_dir / "log.md").write_text("# Change Log\n", encoding="utf-8")
    return CorpusStats(concept_count=len(entries), module_count=len(module_dirs))


def _module_entries(module_name: str, module: object) -> list[CorpusEntry]:
    members = _select_members(module_name, module)[:MAX_MEMBERS_PER_MODULE]
    concept_ids = [cid for cid, _, _, _ in members]
    out: list[CorpusEntry] = []
    for position, (concept_id, title, description, doc) in enumerate(members):
        links = _sibling_links(position, concept_ids)
        out.append(
            CorpusEntry(
                concept_id=concept_id,
                title=title,
                description=description,
                body=_render_body(title, doc, links),
                tags=(module_name, "stdlib"),
                out_links=tuple(links),
            )
        )
    return out


def _select_members(module_name: str, module: object) -> list[tuple[str, str, str, str]]:
    """Return ``(concept_id, title, description, doc)`` rows in deterministic order."""
    prefix = module_name.replace(".", "/")
    rows: list[tuple[str, str, str, str]] = []
    for name in sorted(_public_names(module)):
        member = getattr(module, name)
        if inspect.ismodule(member):
            continue
        if inspect.isclass(member):
            row = _member_row(f"{prefix}/{name}", f"{module_name}.{name}", member)
            if row is not None:
                rows.append(row)
                rows.extend(_method_rows(module_name, prefix, name, member))
        elif inspect.isroutine(member):
            row = _member_row(f"{prefix}/{name}", f"{module_name}.{name}", member)
            if row is not None:
                rows.append(row)
    return _dedupe_casefold(rows)


def _dedupe_casefold(
    rows: list[tuple[str, str, str, str]],
) -> list[tuple[str, str, str, str]]:
    """Drop ids that collide only by case, so a case-insensitive filesystem
    (e.g. macOS) renders the same bundle as a case-sensitive one (e.g. CI)."""
    seen: set[str] = set()
    out: list[tuple[str, str, str, str]] = []
    for row in rows:
        key = row[0].casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _method_rows(
    module_name: str, prefix: str, class_name: str, cls: type
) -> list[tuple[str, str, str, str]]:
    rows: list[tuple[str, str, str, str]] = []
    for name in sorted(_public_names(cls)):
        member = inspect.getattr_static(cls, name, None)
        if not inspect.isroutine(member):
            continue
        row = _member_row(
            f"{prefix}/{class_name}/{name}",
            f"{module_name}.{class_name}.{name}",
            member,
        )
        if row is not None:
            rows.append(row)
    return rows


def _member_row(concept_id: str, title: str, member: object) -> tuple[str, str, str, str] | None:
    # A member named ``index``/``log`` would render to a reserved basename
    # (``index.md``/``log.md``), which the loader skips and the validator rejects;
    # drop it rather than emit an unloadable file.
    if concept_id.rsplit("/", 1)[-1] in _RESERVED_STEMS:
        return None
    doc = inspect.getdoc(member)
    if doc is None:
        return None
    doc = doc.strip()
    if len(doc) < MIN_DOC_CHARS:
        return None
    return concept_id, title, _description(doc), doc


def _public_names(obj: object) -> list[str]:
    return [name for name in dir(obj) if not name.startswith("_")]


def _description(doc: str) -> str:
    first = ""
    for line in doc.splitlines():
        stripped = line.strip()
        if stripped:
            first = stripped
            break
    collapsed = " ".join(first.split())
    if len(collapsed) > MAX_DESCRIPTION_CHARS:
        collapsed = collapsed[: MAX_DESCRIPTION_CHARS - 1].rstrip() + "\u2026"
    return collapsed


def _sibling_links(position: int, concept_ids: list[str]) -> list[str]:
    if len(concept_ids) <= 1:
        return []
    links: list[str] = []
    for offset in range(1, LINKS_PER_CONCEPT + 1):
        sibling = concept_ids[(position + offset) % len(concept_ids)]
        if sibling != concept_ids[position] and sibling not in links:
            links.append(sibling)
    return links


def _render_body(title: str, doc: str, links: list[str]) -> str:
    sections = [f"# {title}", "", doc]
    if links:
        sections.extend(["", "## Related", ""])
        sections.extend(f"- [{_link_title(cid)}](/{cid}.md)" for cid in links)
    return "\n".join(sections) + "\n"


def _link_title(concept_id: str) -> str:
    return concept_id.rsplit("/", 1)[-1]


def _render_concept(entry: CorpusEntry) -> str:
    tags = ", ".join(json.dumps(tag) for tag in entry.tags)
    frontmatter = [
        "---",
        "type: reference",
        f"title: {json.dumps(entry.title)}",
        f"description: {json.dumps(entry.description)}",
        f"tags: [{tags}]",
        "---",
        "",
    ]
    return "\n".join(frontmatter) + entry.body


def _group_by_module(entries: list[CorpusEntry]) -> dict[str, list[CorpusEntry]]:
    grouped: dict[str, list[CorpusEntry]] = {}
    for entry in entries:
        module = entry.tags[0]
        grouped.setdefault(module, []).append(entry)
    return dict(sorted(grouped.items()))


def _render_module_index(module_name: str, entries: list[CorpusEntry]) -> str:
    lines = [f"# {module_name}", ""]
    for entry in sorted(entries, key=lambda e: e.concept_id):
        lines.append(f"* [{entry.title}](/{entry.concept_id}.md) - {entry.description}")
    return "\n".join(lines) + "\n"


def _render_root_index(by_module: dict[str, list[CorpusEntry]], concept_count: int) -> str:
    lines = ["---", "okf_version: '0.1'", "---", "", f"# {CORPUS_NAME}", ""]
    for module_name in by_module:
        rel = module_name.replace(".", "/")
        lines.append(f"* [{module_name}](/{rel}/index.md) - {SOURCE} `{module_name}` reference.")
    lines.extend(_provenance_lines(concept_count, len(by_module)))
    return "\n".join(lines) + "\n"


def _provenance_lines(concept_count: int, module_count: int) -> list[str]:
    return [
        "",
        "## Provenance",
        "",
        f"This bundle is a deterministic OKF rendering of the {SOURCE} docstrings, "
        f"generated by `kosha.bench.corpus.stdlib`. It is an **external, not "
        f"Kosha-authored** corpus used only as the M13 real-model benchmark target "
        f"(DEVELOPMENT_PLAN §7).",
        "",
        f"* Source: {SOURCE} (CPython, the running interpreter).",
        f"* License: {SOURCE_LICENSE}.",
        f"* Concepts: {concept_count} across {module_count} modules.",
        f"* Regenerate: `kosha bench corpus --out bundles/{CORPUS_NAME}` "
        f"(reproducible on the same CPython minor version).",
        "",
        f"Member selection is mechanical: each module's public functions, classes, "
        f"and class methods with a docstring of at least {MIN_DOC_CHARS} characters "
        f"are taken in sorted name order, capped at {MAX_MEMBERS_PER_MODULE} per "
        f"module. Docstrings are reproduced verbatim as concept bodies.",
    ]
