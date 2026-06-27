"""Granularity split: break an over-scoped draft into atomic sub-drafts.

When the ambiguous-band adjudicator returns SPLIT (system_design §4.3) the draft
mixes several concepts and must be re-segmented before each piece is re-resolved
— the one-concept-one-thing rule the M3 lint flags and the dedup loop enforces.
Splitting reuses the M5 extractor's deterministic heading segmentation so a draft
splits exactly the way a fresh ingest would, and each sub-draft inherits the
parent's provenance (``source_id``) and ``type``.
"""

from __future__ import annotations

from collections.abc import Callable

from kosha.extract import ConceptDraft, extract_concepts
from kosha.model import RawDoc, Source, SourceKind
from kosha.providers.base import GenerationProvider

# A function that re-segments an over-scoped draft into atomic sub-drafts.
Splitter = Callable[[ConceptDraft], list[ConceptDraft]]


def split_draft(draft: ConceptDraft, provider: GenerationProvider) -> list[ConceptDraft]:
    """Re-segment ``draft.body`` into sub-drafts via the M5 heading extractor."""
    raw = RawDoc(
        source=Source(
            source_id=draft.source_id,
            kind=SourceKind.MARKDOWN,
            location=draft.source_id,
        ),
        text=draft.body,
    )
    return extract_concepts(raw, provider, type_hint=draft.type)


def make_splitter(provider: GenerationProvider) -> Splitter:
    """Bind a generation provider into a :data:`Splitter` for the resolver."""

    def _split(draft: ConceptDraft) -> list[ConceptDraft]:
        return split_draft(draft, provider)

    return _split
