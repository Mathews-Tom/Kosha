"""Nearest-neighbor candidate lookup — the first step of the dedup decision.

system_design §4.3 opens the dedup path by embedding a candidate concept draft
and asking the M4 embedding index for the existing concepts most similar to it.
The draft is embedded over the same text the index was built from — *description
then body* — so a re-ingested concept matches its own index entry exactly
(cosine ``1.0``), which is what drives the duplicate-rate to zero on a repeated
ingest. The ranked neighbors feed the two-threshold routing (M6 PR-2); this
module ranks candidates and makes no decision itself.
"""

from __future__ import annotations

from kosha.extract import ConceptDraft
from kosha.index.embedding import EmbeddingIndex, Neighbor


def draft_query_text(draft: ConceptDraft) -> str:
    """Return the text a draft is embedded as: its description then its body.

    Mirrors :func:`kosha.index.embedding.index_text` so a draft built from an
    existing concept embeds identically to that concept's index entry. Keeping
    the two in lock-step is what makes a re-ingested concept self-match exactly.
    """
    return f"{draft.description}\n{draft.body}".strip()


def nearest_candidates(
    draft: ConceptDraft, index: EmbeddingIndex, k: int = 5
) -> list[Neighbor]:
    """Return the ``k`` existing concepts most similar to ``draft`` (descending).

    Scores and ordering come straight from the index's cosine query, so the
    result is deterministic for a given index. An empty index yields no
    candidates; ``k <= 0`` is rejected by the underlying query.
    """
    return index.query_text(draft_query_text(draft), k)
