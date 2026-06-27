"""The benchmark query set over the golden Northwind corpus.

Each query names the concept(s) a correct answer must draw on (the
answer-supporting set) and a few keywords a correct answer should mention. These
are the deterministic ground truth the grader scores against, so the quality
numbers are reproducible without an LLM judge.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BenchQuery:
    """One graded benchmark query."""

    id: str
    question: str
    required_concepts: tuple[str, ...]
    answer_keywords: tuple[str, ...]


NORTHWIND_QUERIES: tuple[BenchQuery, ...] = (
    BenchQuery(
        id="gold-return-window",
        question="How long does a Gold member have to return an item?",
        required_concepts=("policies/returns/gold-members",),
        answer_keywords=("45",),
    ),
    BenchQuery(
        id="standard-return-window",
        question="What is the standard return window for a customer?",
        required_concepts=("policies/returns/standard",),
        answer_keywords=("30",),
    ),
    BenchQuery(
        id="refund-settlement-time",
        question="How long do approved refunds take to settle?",
        required_concepts=("policies/refunds",),
        answer_keywords=("business",),
    ),
    BenchQuery(
        id="standard-shipping-time",
        question="How many days does standard shipping take?",
        required_concepts=("policies/shipping",),
        answer_keywords=("business",),
    ),
    BenchQuery(
        id="escalate-complaint",
        question="How should an agent escalate an unhappy customer?",
        required_concepts=("playbooks/escalate-complaint",),
        answer_keywords=("supervisor",),
    ),
    BenchQuery(
        id="exchange-vs-refund",
        question="Can a customer exchange an item instead of taking a refund?",
        required_concepts=("policies/exchanges",),
        answer_keywords=("exchange",),
    ),
    BenchQuery(
        id="membership-perks",
        question="What perks does a higher membership tier give a customer?",
        required_concepts=("entities/membership-tier",),
        answer_keywords=("shipping",),
    ),
    BenchQuery(
        id="handle-return-steps",
        question="What steps does an agent follow to handle a return?",
        required_concepts=("playbooks/handle-return",),
        answer_keywords=("order",),
    ),
)
