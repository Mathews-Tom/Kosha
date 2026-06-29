"""Dedup resolver: decide UPDATE / CREATE / SPLIT for each concept draft.

The resolver realizes ``resolve(ConceptDraft, EmbIndex) -> Resolution``
(system_design §2.2, §4.3): it finds the nearest existing concepts over the M4
embedding index, routes by two similarity thresholds, and reserves an LLM
adjudication for the ambiguous middle band only. Every decision carries a score
and a rationale so the path is auditable (overview §6).
"""

from __future__ import annotations

from kosha.dedup.adjudicate import (
    Adjudication,
    Adjudicator,
    CandidateConcept,
    GenerationAdjudicator,
    LexicalAdjudicator,
    Selection,
    Verdict,
    build_adjudication_prompt,
    build_selection_prompt,
    parse_selection,
    parse_verdict,
)
from kosha.dedup.audit import DecisionRecord, record_decisions, render_decision_log
from kosha.dedup.candidates import draft_query_text, nearest_candidates
from kosha.dedup.decision import (
    DEFAULT_THRESHOLDS,
    Action,
    Route,
    Routing,
    Thresholds,
    route_candidates,
)
from kosha.dedup.resolver import Decision, resolve_draft
from kosha.dedup.split import Splitter, make_splitter, split_draft

__all__ = [
    "DEFAULT_THRESHOLDS",
    "Action",
    "Adjudication",
    "Adjudicator",
    "CandidateConcept",
    "Decision",
    "DecisionRecord",
    "GenerationAdjudicator",
    "LexicalAdjudicator",
    "Route",
    "Routing",
    "Selection",
    "Splitter",
    "Thresholds",
    "Verdict",
    "build_adjudication_prompt",
    "build_selection_prompt",
    "draft_query_text",
    "make_splitter",
    "nearest_candidates",
    "parse_selection",
    "parse_verdict",
    "record_decisions",
    "render_decision_log",
    "resolve_draft",
    "route_candidates",
    "split_draft",
]
