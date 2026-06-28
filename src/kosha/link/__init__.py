"""Cross-linker: discover, validate, and insert inter-concept links.

The link package realizes the cross-linker component (system_design §2.2): an LLM
``relate`` surface proposes inter-concept edges, the deterministic spine validates
them as bundle-relative standard Markdown links (tolerating links to not-yet-written
concepts), inserts them, and computes reverse-edge backlinks.
"""

from __future__ import annotations

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
    "GenerationRelator",
    "LexicalRelator",
    "Relation",
    "Relator",
    "ResolvedLink",
    "build_relate_prompt",
    "bundle_relative_link",
    "classify_link",
    "dangling_links",
    "discover_relations",
    "is_bundle_relative",
    "parse_relations",
]
