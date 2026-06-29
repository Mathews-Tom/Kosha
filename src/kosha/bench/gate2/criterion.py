"""The pre-registered Gate-0 v2 kill criterion (spike S2).

**This criterion is fixed BEFORE any measurement run and MUST NOT be tuned to a
result.** Spike S2 re-opens the Gate-0 question — *does the maintenance loop beat
a good prompt on a buyer-relevant axis?* — after the M13 result tied on a tiny,
clean held-out set (KOSHA_STRATEGIC_ANALYSIS §2.4). The honest way to ask it
again is to pin the bar in code first, then measure against it, so the verdict
cannot be argued into existence after the fact.

The bar (all pre-registered here):

* **Margin.** A quality axis carries a GO only if the loop's median rate exceeds
  the prompt-only baseline's median by at least :data:`QUALITY_MARGIN` *and* the
  win clears the non-determinism noise band — the loop's worst run still beats
  the prompt's best run (non-overlapping intervals). A structural guarantee the
  loop holds *by construction* (zero silent overwrites) is a necessary condition,
  never a quality win — §2.4: "what remains is a guarantee, not a quality win" —
  so it cannot by itself authorize M14+.
* **Sample size.** Each provider cell is scored over at least
  :data:`MIN_CONTRADICTIONS` held-out contradictions, across at least
  :data:`MIN_RUNS` runs (the distribution that the noise band is read from).
* **Regimes.** The held-out contradictions span :data:`REGIMES`, so a win is not
  an artifact of one easy conflict shape.
* **Provider matrix.** The re-test runs across at least :data:`MIN_EMBEDDINGS`
  embeddings and :data:`MIN_GEN_MODELS` generation models; the carrying axis must
  clear the bar on *every* cell, never a cherry-picked one.

GO authorizes M14+. NO-GO keeps Kosha a shipped OSS skill and M14+ stays halted —
an acceptable, expected outcome.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from kosha.bench.gate2.distribution import Distribution

# --- Pre-registered constants (FIXED before measurement; do not tune to a result) ---

# Minimum median(loop) - median(prompt) on a quality axis for it to count as a win.
QUALITY_MARGIN = 0.15
# Held-out contradictions scored per provider cell.
MIN_CONTRADICTIONS = 100
# Runs per cell — the distribution the non-determinism noise band is read from.
MIN_RUNS = 3
# Provider matrix lower bounds.
MIN_EMBEDDINGS = 2
MIN_GEN_MODELS = 2
# Conflict regimes the held-out contradictions must span.
REGIMES: tuple[str, ...] = (
    "numeric",
    "negation",
    "unit",
    "partial",
    "temporal",
    "adversarial",
)
# Quality axes that may carry a GO. A binary structural guarantee is NOT here.
QUALITY_AXES: tuple[str, ...] = ("detection_recall", "safety_rate")


@dataclass(frozen=True)
class AxisDistribution:
    """One quality axis measured as loop and prompt-only run distributions."""

    axis: str
    loop: Distribution
    prompt: Distribution

    @property
    def median_delta(self) -> float:
        return self.loop.median - self.prompt.median

    @property
    def noise_band_excluded(self) -> bool:
        """True iff the loop's worst run still beats the prompt's best run.

        Non-overlapping intervals mean the win is not inside the run-to-run
        non-determinism noise band — the only kind of win Gate-0 v2 counts.
        """
        return self.loop.lo > self.prompt.hi

    def cleared(self, margin: float) -> bool:
        return self.median_delta >= margin and self.noise_band_excluded


@dataclass(frozen=True)
class CellResult:
    """Aggregated Gate-0 v2 measurement for one (embedding, generation) cell."""

    embedding_label: str
    generation_label: str
    axes: tuple[AxisDistribution, ...]
    loop_silent_overwrites: int
    contradictions: int
    regimes: tuple[str, ...]

    def axis(self, name: str) -> AxisDistribution | None:
        for axis in self.axes:
            if axis.axis == name:
                return axis
        return None

    def cleared_axes(self, criterion: Gate2Criterion) -> frozenset[str]:
        """Quality axes whose win clears the margin and the noise band here."""
        return frozenset(
            axis.axis
            for axis in self.axes
            if axis.axis in criterion.quality_axes and axis.cleared(criterion.quality_margin)
        )

    def regimes_covered(self, required: Sequence[str]) -> bool:
        present = set(self.regimes)
        return all(regime in present for regime in required)


@dataclass(frozen=True)
class Gate2Criterion:
    """The pre-registered bar, defaulting to the frozen module constants."""

    quality_margin: float = QUALITY_MARGIN
    min_contradictions: int = MIN_CONTRADICTIONS
    min_runs: int = MIN_RUNS
    min_embeddings: int = MIN_EMBEDDINGS
    min_gen_models: int = MIN_GEN_MODELS
    regimes: tuple[str, ...] = REGIMES
    quality_axes: tuple[str, ...] = QUALITY_AXES

    @classmethod
    def preregistered(cls) -> Gate2Criterion:
        """The frozen Gate-0 v2 bar. Construct it this way; never edit per run."""
        return cls()

    def describe(self) -> str:
        return (
            f"GO only if a quality axis ({', '.join(self.quality_axes)}) clears a "
            f"median margin of >={self.quality_margin:.0%} with the non-determinism "
            f"noise band excluded (loop worst run > prompt best run) on EVERY provider "
            f"cell, the loop never silently overwrites, and the re-test is powered: "
            f">={self.min_contradictions} held-out contradictions spanning "
            f"{len(self.regimes)} regimes ({', '.join(self.regimes)}), >={self.min_runs} "
            f"runs per cell, across >={self.min_embeddings} embeddings x "
            f">={self.min_gen_models} generation models. A structural guarantee (zero "
            f"silent overwrites) is necessary but is not a quality win and cannot "
            f"authorize M14+ on its own. Otherwise NO-GO: keep Kosha an OSS skill; "
            f"M14+ stays halted."
        )


@dataclass(frozen=True)
class Gate2Report:
    """Per-cell Gate-0 v2 results and the verdict derived strictly from the bar."""

    criterion: Gate2Criterion
    cells: tuple[CellResult, ...]
    embeddings: tuple[str, ...]
    generations: tuple[str, ...]
    runs: int
    notes: tuple[str, ...] = field(default_factory=tuple)
    audit_verified: bool | None = None

    @property
    def matrix_powered(self) -> bool:
        return (
            len(self.embeddings) >= self.criterion.min_embeddings
            and len(self.generations) >= self.criterion.min_gen_models
        )

    @property
    def runs_powered(self) -> bool:
        return self.runs >= self.criterion.min_runs

    @property
    def sample_powered(self) -> bool:
        return bool(self.cells) and all(
            cell.contradictions >= self.criterion.min_contradictions for cell in self.cells
        )

    @property
    def regimes_powered(self) -> bool:
        return bool(self.cells) and all(
            cell.regimes_covered(self.criterion.regimes) for cell in self.cells
        )

    @property
    def no_silent_overwrites(self) -> bool:
        return all(cell.loop_silent_overwrites == 0 for cell in self.cells)

    @property
    def powered(self) -> bool:
        """All pre-registered power requirements met — the re-test is admissible."""
        return (
            self.matrix_powered
            and self.runs_powered
            and self.sample_powered
            and self.regimes_powered
        )

    @property
    def carrying_axis(self) -> str | None:
        """The quality axis that cleared the bar on EVERY cell, if any.

        Intersect each cell's cleared axes; a GO requires one common axis so the
        win generalizes across the provider matrix rather than landing on a
        single lucky cell. Deterministic tie-break by the pre-registered order.
        """
        if not self.cells:
            return None
        common: frozenset[str] | None = None
        for cell in self.cells:
            cleared = cell.cleared_axes(self.criterion)
            common = cleared if common is None else (common & cleared)
        if not common:
            return None
        for axis in self.criterion.quality_axes:
            if axis in common:
                return axis
        return None

    @property
    def auditability_ok(self) -> bool:
        """The loop's verifiable no-silent-overwrite guarantee + replayable trail held.

        A binary necessary condition exercised end-to-end (PR-4). It cannot carry a
        GO on its own — a guarantee the loop holds by construction is not a quality
        win (§2.4) — but a re-test that did not verify it is inadmissible.
        """
        return self.audit_verified is True

    @property
    def verdict(self) -> str:
        if not self.powered:
            return "NO-GO"
        if not self.no_silent_overwrites:
            return "NO-GO"
        if not self.auditability_ok:
            return "NO-GO"
        return "GO" if self.carrying_axis is not None else "NO-GO"

    @property
    def authorizes_m14(self) -> bool:
        return self.verdict == "GO"
