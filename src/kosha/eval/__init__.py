"""LLM-surface eval suites.

Each module scores one model-backed surface of the maintenance loop against the
seed labels so quality is measured, not assumed. The extractor eval ships here;
later milestones add dedup/merge/relate/contradict suites (M12 consolidates them).
"""

from __future__ import annotations

from kosha.eval.contradict import (
    ContradictCase,
    ContradictEvalReport,
    evaluate_contradict,
    load_contradict_cases,
)
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
from kosha.eval.relate import (
    RelateCase,
    RelateEvalReport,
    evaluate_relate,
    load_relate_cases,
)

__all__ = [
    "ContradictCase",
    "ContradictEvalReport",
    "DedupEvalReport",
    "DuplicateRateReport",
    "ExtractEvalCase",
    "ExtractEvalReport",
    "MergeCase",
    "MergeEvalCase",
    "MergeEvalReport",
    "RelateCase",
    "RelateEvalReport",
    "evaluate_contradict",
    "evaluate_dedup",
    "evaluate_duplicate_rate",
    "evaluate_extractor",
    "evaluate_merge",
    "evaluate_relate",
    "load_contradict_cases",
    "load_merge_cases",
    "load_relate_cases",
]
