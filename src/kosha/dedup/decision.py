"""Two-threshold routing: turn ranked candidates into a routing decision.

system_design §4.3 keeps the LLM call rare by bracketing the embedding
nearest-neighbor score with two thresholds:

* score ``>= high`` — clearly the same concept           → UPDATE
* score ``< low`` (or no candidate) — clearly novel      → CREATE
* ``low <= score < high`` — the ambiguous band           → adjudicate (LLM)

Routing is deterministic and records a rationale for the audit log; the
ambiguous band is the only path that reaches a model (M6 PR-3). Thresholds are a
per-bundle tunable (system_design §4.5); the defaults are calibrated for the
local lexical embedding so the offline benchmark and eval route sensibly.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from kosha.index.embedding import Neighbor


class Action(StrEnum):
    """The terminal dedup decision for a draft."""

    UPDATE = "update"
    CREATE = "create"
    SPLIT = "split"


class Route(StrEnum):
    """Where two-threshold routing sends a draft before any LLM call."""

    UPDATE = "update"
    CREATE = "create"
    ADJUDICATE = "adjudicate"


@dataclass(frozen=True)
class Thresholds:
    """High/low cosine cutoffs bracketing the ambiguous band.

    ``high`` and ``low`` lie in ``[0, 1]`` with ``low <= high``. The band is the
    half-open interval ``[low, high)``: a score at ``high`` is an UPDATE and a
    score below ``low`` is a CREATE.
    """

    high: float
    low: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.low <= self.high <= 1.0:
            raise ValueError(
                "thresholds must satisfy 0 <= low <= high <= 1, "
                f"got low={self.low}, high={self.high}"
            )


# Calibrated for the default local lexical embedding: near-identical text
# (cosine ~1.0, e.g. a re-ingest) auto-updates, clearly-unrelated text
# (cosine < 0.15) auto-creates, and everything between is adjudicated.
DEFAULT_THRESHOLDS = Thresholds(high=0.95, low=0.15)


@dataclass(frozen=True)
class Routing:
    """The outcome of two-threshold routing over a draft's candidates."""

    route: Route
    candidate: Neighbor | None
    score: float
    rationale: str


def route_candidates(
    candidates: list[Neighbor], thresholds: Thresholds = DEFAULT_THRESHOLDS
) -> Routing:
    """Route a draft to UPDATE / CREATE / ADJUDICATE by its top candidate."""
    if not candidates:
        return Routing(Route.CREATE, None, 0.0, "no candidates -> CREATE")
    top = candidates[0]
    if top.score >= thresholds.high:
        return Routing(
            Route.UPDATE,
            top,
            top.score,
            f"score {top.score:.3f} >= high {thresholds.high} -> UPDATE {top.concept_id}",
        )
    if top.score < thresholds.low:
        return Routing(
            Route.CREATE,
            top,
            top.score,
            f"score {top.score:.3f} < low {thresholds.low} -> CREATE",
        )
    return Routing(
        Route.ADJUDICATE,
        top,
        top.score,
        f"score {top.score:.3f} in [{thresholds.low}, {thresholds.high}) -> adjudicate",
    )
