"""Insert discovered links into concept bodies and compute reverse-edge backlinks.

The write half of the cross-linker (system_design §2.2). Discovered relations are
materialized as a managed ``# Related`` section of bundle-relative standard
Markdown links; backlinks ("cited by", system_design §3) as a managed
``# Backlinks`` section of the reverse edges.

Both sections are **derived state**: every pass strips and regenerates them, so
re-running the cross-linker over an already-linked bundle reproduces it
byte-for-byte (idempotent). Forward edges — a concept's prose links plus its
``# Related`` links — drive backlink computation; the ``# Backlinks`` section is
excluded from them so reverse edges never feed back into the graph. ``# Related``
and ``# Backlinks`` are therefore reserved headings owned by the cross-linker.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

from kosha.link.paths import bundle_relative_link
from kosha.link.relate import Relation, Relator, discover_relations
from kosha.merge import write_concept
from kosha.model import Bundle, Concept
from kosha.okf.parse import extract_out_links

RELATED_HEADING = "Related"
BACKLINKS_HEADING = "Backlinks"
_RELATED = f"# {RELATED_HEADING}"
_BACKLINKS = f"# {BACKLINKS_HEADING}"


def strip_managed_sections(body: str) -> str:
    """Return ``body`` with the managed ``# Related`` and ``# Backlinks`` sections cut.

    The cross-linker appends both at the end, so cutting from the first managed
    heading onward leaves the prose and any ``# Citations`` block intact.
    """
    return _cut_from(body, (_RELATED, _BACKLINKS))


def forward_targets(concept_id: str, body: str) -> list[str]:
    """Return a concept's forward-edge targets: prose + ``# Related`` links.

    The ``# Backlinks`` section is stripped first so reverse edges are not counted
    as forward edges.
    """
    return extract_out_links(concept_id, _cut_from(body, (_BACKLINKS,)))


def compute_backlinks(bundle: Bundle) -> dict[str, list[str]]:
    """Map each concept id to the concept ids that link to it (reverse edges).

    Built from forward edges over sorted sources, so ordering is deterministic.
    Reverse edges to a dangling target are included; callers materialize only the
    targets the bundle actually contains.
    """
    backlinks: dict[str, list[str]] = {}
    for source in sorted(bundle.concepts):
        for target in forward_targets(source, bundle.concepts[source].body):
            sources = backlinks.setdefault(target, [])
            if source not in sources:
                sources.append(source)
    return backlinks


def apply_links(bundle: Bundle, relations: Sequence[Relation]) -> Bundle:
    """Insert discovered forward links and regenerate backlink sections.

    Idempotent: managed sections are stripped before rebuilding, so calling this
    with the full discovered relation set reproduces the same bundle each time.
    ``relations`` must be discovered over stripped content (see :func:`crosslink`).
    """
    related = _group_targets(relations)
    staged: dict[str, Concept] = {}
    for concept_id, concept in bundle.concepts.items():
        content = strip_managed_sections(concept.body)
        sections = _related_section(bundle, related.get(concept_id, []))
        staged[concept_id] = _rebuild(concept, _assemble(content, sections))
    staged_bundle = bundle.model_copy(update={"concepts": staged})

    backlinks = compute_backlinks(staged_bundle)
    linked: dict[str, Concept] = {}
    for concept_id, concept in staged.items():
        sections = _backlinks_section(bundle, backlinks.get(concept_id, []))
        linked[concept_id] = _rebuild(concept, _assemble(concept.body, sections))
    return bundle.model_copy(update={"concepts": linked})


def crosslink(bundle: Bundle, relator: Relator) -> Bundle:
    """Discover and apply links end-to-end: strip, relate, insert, backlink.

    Discovery runs over content with managed sections stripped so the same edges
    are found every pass, making the whole operation idempotent.
    """
    stripped = bundle.model_copy(
        update={
            "concepts": {
                concept_id: _rebuild(concept, strip_managed_sections(concept.body))
                for concept_id, concept in bundle.concepts.items()
            }
        }
    )
    return apply_links(bundle, discover_relations(stripped, relator))


def changed_concept_ids(before: Bundle, after: Bundle) -> list[str]:
    """Return the sorted ids of concepts whose body changed between two bundles."""
    return sorted(
        concept_id
        for concept_id, concept in after.concepts.items()
        if concept_id not in before.concepts or before.concepts[concept_id].body != concept.body
    )


def write_concepts(root: Path, bundle: Bundle, concept_ids: Iterable[str]) -> list[Path]:
    """Serialize the named concepts under ``root`` through the M2 writer guards."""
    return [write_concept(root, bundle.concepts[concept_id]) for concept_id in concept_ids]


def _group_targets(relations: Sequence[Relation]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for relation in relations:
        targets = grouped.setdefault(relation.source, [])
        if relation.target not in targets:
            targets.append(relation.target)
    return grouped


def _related_section(bundle: Bundle, targets: Sequence[str]) -> list[str]:
    if not targets:
        return []
    return [_render_section(RELATED_HEADING, [_link_item(bundle, target) for target in targets])]


def _backlinks_section(bundle: Bundle, sources: Sequence[str]) -> list[str]:
    if not sources:
        return []
    return [_render_section(BACKLINKS_HEADING, [_link_item(bundle, source) for source in sources])]


def _render_section(heading: str, items: list[str]) -> str:
    return "\n".join([f"# {heading}", "", *items])


def _link_item(bundle: Bundle, concept_id: str) -> str:
    concept = bundle.concepts.get(concept_id)
    text = concept.frontmatter.title if concept and concept.frontmatter.title else concept_id
    return f"* {bundle_relative_link(concept_id, text)}"


def _assemble(content: str, sections: list[str]) -> str:
    blocks = [content.rstrip("\n"), *sections]
    body = "\n\n".join(block for block in blocks if block)
    return f"{body}\n" if body else "\n"


def _rebuild(concept: Concept, body: str) -> Concept:
    return concept.model_copy(
        update={"body": body, "out_links": forward_targets(concept.concept_id, body)}
    )


def _cut_from(body: str, headings: tuple[str, ...]) -> str:
    lines = body.split("\n")
    for index, line in enumerate(lines):
        if line.strip() in headings:
            return "\n".join(lines[:index]).rstrip("\n")
    return body
