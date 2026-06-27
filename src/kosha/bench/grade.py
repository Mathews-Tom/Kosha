"""Deterministic grading of a strategy's answer to a benchmark query.

Quality is measured two ways, both reproducible:

* **concept recall** — the fraction of the query's required concepts whose content
  reached the generator (the answer-supporting set). This is the premise question:
  did the strategy surface the right knowledge?
* **answer-keyword recall** — the fraction of expected keywords present in the
  generated answer text.
"""

from __future__ import annotations

from dataclasses import dataclass

from kosha.bench.queries import BenchQuery
from kosha.bench.strategies import RetrievedContext


@dataclass(frozen=True)
class QueryGrade:
    """The graded outcome for one (strategy, query) pair."""

    query_id: str
    concept_recall: float
    answered: bool
    keyword_hits: int
    keyword_total: int

    @property
    def keyword_recall(self) -> float:
        if self.keyword_total == 0:
            return 1.0
        return self.keyword_hits / self.keyword_total


def grade_query(query: BenchQuery, context: RetrievedContext, answer: str) -> QueryGrade:
    """Grade one answer: concept recall over context, keyword recall over the answer."""
    required = set(query.required_concepts)
    retrieved = set(context.concept_ids)
    found = required & retrieved
    concept_recall = len(found) / len(required) if required else 1.0
    answer_lower = answer.lower()
    hits = sum(1 for kw in query.answer_keywords if kw.lower() in answer_lower)
    return QueryGrade(
        query_id=query.id,
        concept_recall=concept_recall,
        answered=required <= retrieved,
        keyword_hits=hits,
        keyword_total=len(query.answer_keywords),
    )
