"""Bundle-relative link construction and target validation for the cross-linker.

The cross-linker emits only **standard, bundle-relative** Markdown links —
``[text](/path/to/concept.md)`` — never Obsidian ``[[wikilinks]]`` (system_design
§3 writer guards, OKF §6.4). A discovered link is *valid or intentionally
dangling*: a target that resolves to a concept the bundle does not (yet) contain
is tolerated — a link to not-yet-written knowledge — not rejected (OKF §6.4 / §7
permissive consumption).

Link resolution itself lives in :mod:`kosha.okf.parse` (``resolve_link_target``),
the single source of truth shared with the document parser; this module classifies
a resolved target against a loaded :class:`~kosha.model.Bundle`.
"""

from __future__ import annotations

from dataclasses import dataclass

from kosha.model import Bundle
from kosha.okf.parse import resolve_link_target


@dataclass(frozen=True)
class ResolvedLink:
    """A bundle link target resolved to a concept id and its presence.

    ``present`` is ``False`` for an *intentionally dangling* link — a well-formed
    bundle-relative target whose concept the bundle does not yet contain.
    """

    concept_id: str
    present: bool

    @property
    def dangling(self) -> bool:
        """True when the target concept is absent from the bundle."""
        return not self.present


def bundle_relative_link(target_id: str, text: str) -> str:
    """Render a standard, bundle-relative Markdown link to a concept id.

    The target is always absolute (begins with ``/``) and stable when files move,
    the form OKF §6.4 recommends and the writer guards require.
    """
    return f"[{text}](/{target_id}.md)"


def is_bundle_relative(target: str) -> bool:
    """True if a Markdown link target is an absolute bundle-relative path."""
    return target.startswith("/")


def classify_link(source_id: str, target: str, bundle: Bundle) -> ResolvedLink | None:
    """Resolve ``target`` (as written in ``source_id``'s body) and classify it.

    Returns ``None`` when ``target`` is not an in-bundle link (an external URL, a
    bare anchor, a non-``.md`` target, or a path escaping the bundle root); a
    :class:`ResolvedLink` otherwise, marking whether the target concept exists.
    """
    concept_id = resolve_link_target(source_id, target)
    if concept_id is None:
        return None
    return ResolvedLink(concept_id=concept_id, present=concept_id in bundle.concepts)


def dangling_links(bundle: Bundle) -> dict[str, list[str]]:
    """Map each concept id to its out-links whose target concept is absent.

    These are the *intentionally dangling* links the spec tolerates — surfaced so
    the cross-linker and validator can report (not reject) links to not-yet-written
    concepts. Concepts with no dangling links are omitted; out-link order is kept.
    """
    present = set(bundle.concepts)
    result: dict[str, list[str]] = {}
    for concept_id, concept in bundle.concepts.items():
        missing = [target for target in concept.out_links if target not in present]
        if missing:
            result[concept_id] = missing
    return result
