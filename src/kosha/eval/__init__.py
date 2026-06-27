"""LLM-surface eval suites.

Each module scores one model-backed surface of the maintenance loop against the
seed labels so quality is measured, not assumed. The extractor eval ships here;
later milestones add dedup/merge/relate/contradict suites (M12 consolidates them).
"""

from __future__ import annotations

from kosha.eval.extract import (
    ExtractEvalCase,
    ExtractEvalReport,
    evaluate_extractor,
)

__all__ = [
    "ExtractEvalCase",
    "ExtractEvalReport",
    "evaluate_extractor",
]
