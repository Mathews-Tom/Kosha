"""Real-model, held-out benchmark suite (DEVELOPMENT_PLAN §7 M13).

Gate 0 of the post-MVP plan asks one question with a real embedding and a real
LLM, on an external corpus: does the maintenance loop beat a tuned RAG baseline
and a prompt-only baseline well enough to be a product rather than a skill? This
package holds the held-out label loaders, the prompt-only baseline, and the
runner that produces the three-way comparison and the go/no-go verdict.
"""

from __future__ import annotations

from kosha.bench.realworld.labels import (
    MAINTENANCE_ACTIONS,
    MAINTENANCE_KINDS,
    MaintenanceCase,
    load_maintenance,
    load_queries,
)
from kosha.bench.realworld.promptonly import (
    PromptDecision,
    PromptOnlyAnswer,
    PromptOnlyBaseline,
)
from kosha.bench.realworld.runner import (
    KILL_CRITERION,
    DriftResult,
    MaintenanceResult,
    QueryStrategyResult,
    RealworldConfig,
    RealworldReport,
    render_realworld_report,
    run_realworld,
)

__all__ = [
    "KILL_CRITERION",
    "MAINTENANCE_ACTIONS",
    "MAINTENANCE_KINDS",
    "DriftResult",
    "MaintenanceCase",
    "MaintenanceResult",
    "PromptDecision",
    "PromptOnlyAnswer",
    "PromptOnlyBaseline",
    "QueryStrategyResult",
    "RealworldConfig",
    "RealworldReport",
    "load_maintenance",
    "load_queries",
    "render_realworld_report",
    "run_realworld",
]
