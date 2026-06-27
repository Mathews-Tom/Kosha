"""Dedup resolver: decide UPDATE / CREATE / SPLIT for each concept draft.

The resolver realizes ``resolve(ConceptDraft, EmbIndex) -> Resolution``
(system_design §2.2, §4.3): it finds the nearest existing concepts over the M4
embedding index, routes by two similarity thresholds, and reserves an LLM
adjudication for the ambiguous middle band only. Every decision carries a score
and a rationale so the path is auditable (overview §6).
"""

from __future__ import annotations

from kosha.dedup.candidates import draft_query_text, nearest_candidates

__all__ = [
    "draft_query_text",
    "nearest_candidates",
]
