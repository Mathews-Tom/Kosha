"""LLM-surface eval suites.

Each module scores one model-backed surface of the maintenance loop against the
seed labels so quality is measured, not assumed. The extractor eval ships here;
later milestones add dedup/merge/relate/contradict suites (M12 consolidates them).
"""

from __future__ import annotations

from kosha.eval.dedup import (
    DedupEvalReport,
    DuplicateRateReport,
    evaluate_dedup,
    evaluate_duplicate_rate,
)
from kosha.eval.extract import (
    ExtractEvalCase,
    ExtractEvalReport,
    evaluate_extractor,
)
from kosha.eval.merge import (
    MergeCase,
    MergeEvalCase,
    MergeEvalReport,
    evaluate_merge,
    load_merge_cases,
)

__all__ = [
    "DedupEvalReport",
    "DuplicateRateReport",
    "ExtractEvalCase",
    "ExtractEvalReport",
    "MergeCase",
    "MergeEvalCase",
    "MergeEvalReport",
    "evaluate_dedup",
    "evaluate_duplicate_rate",
    "evaluate_extractor",
    "evaluate_merge",
    "load_merge_cases",
]
