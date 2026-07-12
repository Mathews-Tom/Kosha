"""Concept extractor: propose candidate concepts from a :class:`RawDoc`.

The extractor realizes ``extract(RawDoc) -> list[ConceptDraft]`` (system_design
§2.2). Two responsibilities, split so the quality-critical part stays testable:

* **Boundary detection is deterministic.** Concepts are segmented on Markdown
  ``#`` headings — one draft per heading section, or the whole document when it
  has no headings. This is the "one concept, one thing" boundary the granularity
  lint (M3) and the dedup ``split`` branch (M6) are the safety net for, so it
  must be reproducible rather than model-dependent.
* **Description is generated through the provider interface.** Each draft's
  one-line description comes from the configured :class:`GenerationProvider`, so
  a real model sharpens it while the deterministic local provider keeps the
  pipeline reproducible and offline.

The extractor never re-fetches a source; it reads only the normalized
``RawDoc.text`` an ingest adapter produced.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from kosha.model import RawDoc
from kosha.providers.base import GenerationProvider

# ATX heading: up to three leading spaces, 1-6 '#', a space, then the title text.
_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*)$")


@dataclass(frozen=True)
class ConceptDraft:
    """A candidate concept proposed from a source, before dedup/merge.

    ``source_id`` carries provenance back to the originating :class:`Source` so
    the dedup resolver (M6) and merge/writer (M7) can stamp claims with it.
    ``source_run_id`` / ``evidence_sha256`` carry the originating
    :class:`~kosha.model.RawDoc`'s evidence identity (DEVELOPMENT_PLAN.md M3)
    so a minted claim resolves back to stored evidence without re-fetching.
    """

    title: str
    body: str
    description: str
    type: str
    source_id: str
    source_run_id: str | None = None
    evidence_sha256: str | None = None


def extract_concepts(
    raw: RawDoc,
    provider: GenerationProvider,
    *,
    type_hint: str = "concept",
) -> list[ConceptDraft]:
    """Segment ``raw`` into candidate concepts; always returns at least one."""
    fallback_title = raw.source.title or raw.source.source_id
    drafts: list[ConceptDraft] = []
    for title, body in _segment(raw.text):
        resolved = title or fallback_title
        drafts.append(
            ConceptDraft(
                title=resolved,
                body=body,
                description=_describe(resolved, body, provider),
                type=type_hint,
                source_id=raw.source.source_id,
                source_run_id=raw.source_run_id,
                evidence_sha256=raw.evidence_sha256,
            )
        )
    return drafts


def _segment(text: str) -> list[tuple[str | None, str]]:
    """Split ``text`` into (heading, body) sections on Markdown headings.

    Content before the first heading is folded into that first section; a
    document with no headings yields a single whole-document section.
    """
    sections: list[tuple[str | None, list[str]]] = []
    preamble: list[str] = []
    title: str | None = None
    body: list[str] = []
    seen_heading = False
    for line in text.splitlines():
        match = _HEADING.match(line)
        if match:
            if not seen_heading:
                preamble = body
                seen_heading = True
            else:
                sections.append((title, body))
            title = match.group(2).strip() or None
            body = []
        else:
            body.append(line)
    if not seen_heading:
        return [(None, "\n".join(body).strip())]
    sections.append((title, body))
    if any(line.strip() for line in preamble):
        first_title, first_body = sections[0]
        sections[0] = (first_title, preamble + first_body)
    return [(section_title, "\n".join(lines).strip()) for section_title, lines in sections]


def _describe(title: str, body: str, provider: GenerationProvider) -> str:
    """Generate a one-line description for a draft via the provider interface."""
    if not body:
        return title
    generated = provider.generate(query=title, context=body).text.strip()
    return generated or title
