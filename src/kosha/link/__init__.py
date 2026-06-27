"""Cross-linker: discover, validate, and insert inter-concept links.

The link package realizes the cross-linker component (system_design §2.2): an LLM
``relate`` surface proposes inter-concept edges, the deterministic spine validates
them as bundle-relative standard Markdown links (tolerating links to not-yet-written
concepts), inserts them, and computes reverse-edge backlinks.
"""

from __future__ import annotations

from kosha.link.edits import (
    BACKLINKS_HEADING,
    RELATED_HEADING,
    apply_links,
    changed_concept_ids,
    compute_backlinks,
    crosslink,
    forward_targets,
    strip_managed_sections,
    write_concepts,
)
from kosha.link.paths import (
    ResolvedLink,
    bundle_relative_link,
    classify_link,
    dangling_links,
    is_bundle_relative,
)
from kosha.link.relate import (
    GenerationRelator,
    LexicalRelator,
    Relation,
    Relator,
    build_relate_prompt,
    discover_relations,
    parse_relations,
)

__all__ = [
    "BACKLINKS_HEADING",
    "RELATED_HEADING",
    "GenerationRelator",
    "LexicalRelator",
    "Relation",
    "Relator",
    "ResolvedLink",
    "apply_links",
    "build_relate_prompt",
    "bundle_relative_link",
    "changed_concept_ids",
    "classify_link",
    "compute_backlinks",
    "crosslink",
    "dangling_links",
    "discover_relations",
    "forward_targets",
    "is_bundle_relative",
    "parse_relations",
    "strip_managed_sections",
    "write_concepts",
]
