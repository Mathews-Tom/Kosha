"""CREATE path: mint a new concept from a draft and write it via M2 guards.

A CREATE turns a :class:`~kosha.extract.ConceptDraft` into a
:class:`~kosha.model.Concept` whose body is the deterministic projection of its
claims (one claim per draft paragraph, each stamped with the source's provenance)
and writes it as plain OKF markdown through the M2 serializer — which enforces the
writer conformance guards (no wikilinks). The on-disk artifact is ordinary OKF;
the claim layer rides along in memory for later supersede merges.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from kosha.extract import ConceptDraft
from kosha.merge.claims import make_claim, render_body
from kosha.model import Claim, Concept, Frontmatter, Source
from kosha.okf.serialize import serialize_concept

# A blank-line paragraph boundary (one or more empty/whitespace-only lines).
_PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n")
# A "# Citations" (any heading level) section header, defensively skipped so a
# draft that already carries a rendered citations block does not become a claim.
_CITATIONS_HEADING = re.compile(r"^#{1,6}\s+Citations\b", re.IGNORECASE)


def source_citation(source: Source) -> str:
    """Return the citation string recorded on claims derived from ``source``."""
    if source.title:
        return f"{source.title} ({source.location})"
    return source.location


def segment_statements(body: str) -> list[str]:
    """Split a draft body into claim statements: one per non-empty paragraph.

    Paragraphs are the supersede unit, so a later ingest can retire a single
    statement without disturbing the rest of the body. A ``# Citations`` block is
    skipped rather than captured as a claim.
    """
    statements: list[str] = []
    for block in _PARAGRAPH_BREAK.split(body):
        statement = block.strip()
        if not statement or _CITATIONS_HEADING.match(statement):
            continue
        statements.append(statement)
    return statements


def claims_from_draft(
    draft: ConceptDraft, source: Source, asserted_at: datetime, *, reviewer: str | None = None
) -> list[Claim]:
    """Build the initial claim set for a draft, stamped with source provenance.

    Falls back to the draft's one-line description when the body has no
    paragraphs, so a concept always has at least one provenance-bearing claim.
    """
    citation = source_citation(source)
    statements = segment_statements(draft.body) or [draft.description]
    return [
        make_claim(
            statement, source.source_id, asserted_at, citations=[citation], reviewer=reviewer
        )
        for statement in statements
    ]


def create_concept(
    draft: ConceptDraft,
    concept_id: str,
    source: Source,
    asserted_at: datetime,
    *,
    reviewer: str | None = None,
) -> Concept:
    """Mint a new :class:`Concept` from ``draft`` with claim-projected body."""
    claims = claims_from_draft(draft, source, asserted_at, reviewer=reviewer)
    frontmatter = Frontmatter(
        type=draft.type,
        title=draft.title,
        description=draft.description,
        timestamp=asserted_at,
    )
    return Concept(
        concept_id=concept_id,
        frontmatter=frontmatter,
        body=render_body(claims),
        claims=claims,
    )


def write_concept(root: Path, concept: Concept) -> Path:
    """Serialize ``concept`` through the M2 writer guards and write it under ``root``.

    The path is ``<root>/<concept_id>.md``; parent directories are created. The
    serializer rejects non-OKF wikilinks, so a guard violation raises here rather
    than producing a non-conformant file.
    """
    markdown = serialize_concept(concept)
    path = root / f"{concept.concept_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    return path
