"""The real-model, held-out benchmark runner and its go/no-go verdict (M13).

This drives the one Gate-0 question (KOSHA_STRATEGIC_ANALYSIS §5) with a real
embedding and a real LLM on the external corpus, and produces a single report:

* **Three-way retrieval/answer table** over the held-out query set — Kosha hybrid
  vs tuned RAG vs the prompt-only baseline (concept recall, answer-keyword recall,
  context tokens, total tokens).
* **Maintenance routing** over the held-out cases — the Kosha loop (embedding
  routing + reserved LLM adjudication) vs prompt-only (one-shot LLM), scored
  overall and per dedup / novel / contradiction kind.
* **Drift** across at least 50 sequential ingests driven through ``ingest()`` with
  the real providers: maintenance routing accuracy is re-measured on the grown
  corpus, and the deterministic edit-drift fidelity check is reused, so a quality
  regression as the corpus grows is caught.

The kill criterion is fixed in code below, *before* any run, exactly as Gate 0
requires. The runner takes injected providers, so the deterministic parts run
offline under pytest and the same code produces the real verdict when an endpoint
is configured.
"""

from __future__ import annotations

import statistics
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from kosha.bench.acceptance import measure_fidelity
from kosha.bench.grade import grade_query
from kosha.bench.queries import BenchQuery
from kosha.bench.realworld.labels import MaintenanceCase, load_maintenance, load_queries
from kosha.bench.realworld.promptonly import PromptOnlyBaseline
from kosha.bench.strategies import (
    HybridStrategy,
    RetrievedContext,
    TunedRagStrategy,
)
from kosha.dedup import (
    DEFAULT_THRESHOLDS,
    Action,
    Adjudicator,
    GenerationAdjudicator,
    Thresholds,
    resolve_draft,
)
from kosha.extract import ConceptDraft
from kosha.index import EmbeddingIndex
from kosha.index.embedding import index_text
from kosha.model import Bundle
from kosha.okf import load_bundle
from kosha.pipeline import ingest
from kosha.providers.base import EmbeddingProvider, Generation, GenerationProvider
from kosha.providers.tokens import count_tokens

# A function mapping a maintenance case to a (action, concept_id) routing decision.
_RouteFn = Callable[["MaintenanceCase"], tuple[str, str | None]]

# --- Kill criterion (fixed BEFORE the run; KOSHA_STRATEGIC_ANALYSIS §5 Gate 0) ---
# The maintenance loop is a product only if ALL of these hold; otherwise Kosha is
# a skill and ships as an OSS library/skill — M14+ does not begin.
#  1. Loop maintenance accuracy beats prompt-only by a margin a buyer would notice.
#  2. Maintenance accuracy does not degrade as the corpus grows over >=50 ingests.
#  3. Edit-drift fidelity holds across the whole run.
NOTABLE_MARGIN = 0.10
DRIFT_TOLERANCE = 0.05
MIN_INGESTS = 50
KILL_CRITERION = (
    "GO only if (1) loop maintenance accuracy exceeds prompt-only by at least "
    f"{NOTABLE_MARGIN:.0%}, (2) maintenance accuracy does not drop by more than "
    f"{DRIFT_TOLERANCE:.0%} across >={MIN_INGESTS} sequential ingests, and (3) "
    "edit-drift fidelity holds. Otherwise NO-GO: ship Kosha as an OSS skill and "
    "halt M14+."
)


@dataclass(frozen=True)
class QueryStrategyResult:
    """Aggregated held-out-query metrics for one retrieval strategy."""

    name: str
    concept_recall: float
    keyword_recall: float
    avg_context_tokens: float
    avg_total_tokens: float


@dataclass(frozen=True)
class MaintenanceResult:
    """Maintenance routing accuracy for one decider, overall and per kind."""

    name: str
    correct: int
    total: int
    by_kind: dict[str, float]

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0


@dataclass(frozen=True)
class DriftResult:
    """Maintenance accuracy before and after >=50 ingests, plus fidelity."""

    ingests: int
    accuracy_start: float
    accuracy_end: float
    fidelity_ok: bool


@dataclass(frozen=True)
class RealworldConfig:
    """Inputs for one real-world benchmark run."""

    corpus: Path
    queries: Path
    maintenance: Path
    guidance: Path
    ingests: int = MIN_INGESTS
    candidate_k: int = 6
    drift_seed_concepts: int = 150
    max_queries: int | None = None


@dataclass(frozen=True)
class RealworldReport:
    """The full M13 outcome: setup, three measurements, and a verdict."""

    embedding_provider: str
    generation_provider: str
    corpus_path: str
    concept_count: int
    query_count: int
    queries: tuple[QueryStrategyResult, ...]
    maintenance: tuple[MaintenanceResult, ...]
    drift: DriftResult

    def by_strategy(self, name: str) -> QueryStrategyResult:
        for result in self.queries:
            if result.name == name:
                return result
        raise KeyError(name)

    def maintenance_by_name(self, name: str) -> MaintenanceResult:
        for result in self.maintenance:
            if result.name == name:
                return result
        raise KeyError(name)

    @property
    def maintenance_delta(self) -> float:
        return self.maintenance_by_name("kosha_loop").accuracy - self.maintenance_by_name(
            "prompt_only"
        ).accuracy

    @property
    def beats_prompt_only(self) -> bool:
        return self.maintenance_delta >= NOTABLE_MARGIN

    @property
    def no_degradation(self) -> bool:
        return (
            self.drift.ingests >= MIN_INGESTS
            and self.drift.fidelity_ok
            and self.drift.accuracy_end >= self.drift.accuracy_start - DRIFT_TOLERANCE
        )

    @property
    def verdict(self) -> str:
        return "GO" if self.beats_prompt_only and self.no_degradation else "NO-GO"


def run_realworld(
    config: RealworldConfig,
    embedding_provider: EmbeddingProvider,
    generation_provider: GenerationProvider,
    *,
    adjudicator: Adjudicator | None = None,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
    work_dir: Path | None = None,
) -> RealworldReport:
    """Run the three-way comparison and the drift probe; return the verdict report."""
    bundle = load_bundle(config.corpus)
    queries = load_queries(config.queries)
    if config.max_queries is not None:
        queries = queries[: config.max_queries]
    cases = load_maintenance(config.maintenance)
    guidance = config.guidance.read_text(encoding="utf-8")
    loop_adjudicator = adjudicator or GenerationAdjudicator(generation_provider)

    index = EmbeddingIndex.build(bundle, embedding_provider)
    query_results = _run_queries(
        bundle, index, embedding_provider, generation_provider, queries, guidance, config
    )
    maintenance_results = _run_maintenance(
        bundle, index, generation_provider, cases, guidance, config, loop_adjudicator, thresholds
    )
    drift = _run_drift(
        bundle,
        embedding_provider,
        generation_provider,
        cases,
        config,
        loop_adjudicator,
        thresholds,
        work_dir,
    )
    return RealworldReport(
        embedding_provider=embedding_provider.name,
        generation_provider=generation_provider.name,
        corpus_path=str(config.corpus),
        concept_count=len(bundle.concepts),
        query_count=len(queries),
        queries=query_results,
        maintenance=maintenance_results,
        drift=drift,
    )


def _run_queries(
    bundle: Bundle,
    index: EmbeddingIndex,
    embedding_provider: EmbeddingProvider,
    generation_provider: GenerationProvider,
    queries: tuple[BenchQuery, ...],
    guidance: str,
    config: RealworldConfig,
) -> tuple[QueryStrategyResult, ...]:
    hybrid = HybridStrategy(bundle, index)
    tuned_rag = TunedRagStrategy(bundle, embedding_provider)
    prompt_only = PromptOnlyBaseline(
        bundle, index, generation_provider, guidance=guidance, candidate_k=config.candidate_k
    )

    def answer(name: str, query: BenchQuery) -> tuple[RetrievedContext, Generation]:
        if name == "prompt_only":
            result = prompt_only.answer(query.question)
            return result.context, result.generation
        strategy = hybrid if name == "kosha_hybrid" else tuned_rag
        context = strategy.retrieve(query.question)
        return context, generation_provider.generate(query.question, context.text)

    results: list[QueryStrategyResult] = []
    for name in ("kosha_hybrid", "tuned_rag", "prompt_only"):
        concept_recall: list[float] = []
        keyword_recall: list[float] = []
        context_tokens: list[int] = []
        total_tokens: list[int] = []
        for query in queries:
            context, generation = answer(name, query)
            grade = grade_query(query, context, generation.text)
            concept_recall.append(grade.concept_recall)
            keyword_recall.append(grade.keyword_recall)
            context_tokens.append(count_tokens(context.text))
            total_tokens.append(generation.usage.total_tokens)
        results.append(
            QueryStrategyResult(
                name=name,
                concept_recall=statistics.fmean(concept_recall) if concept_recall else 0.0,
                keyword_recall=statistics.fmean(keyword_recall) if keyword_recall else 0.0,
                avg_context_tokens=statistics.fmean(context_tokens) if context_tokens else 0.0,
                avg_total_tokens=statistics.fmean(total_tokens) if total_tokens else 0.0,
            )
        )
    return tuple(results)


def _run_maintenance(
    bundle: Bundle,
    index: EmbeddingIndex,
    generation_provider: GenerationProvider,
    cases: tuple[MaintenanceCase, ...],
    guidance: str,
    config: RealworldConfig,
    adjudicator: Adjudicator,
    thresholds: Thresholds,
) -> tuple[MaintenanceResult, ...]:
    concept_texts = {cid: index_text(concept) for cid, concept in bundle.concepts.items()}
    prompt_only = PromptOnlyBaseline(
        bundle, index, generation_provider, guidance=guidance, candidate_k=config.candidate_k
    )

    def loop_route(case: MaintenanceCase) -> tuple[str, str | None]:
        return _loop_decision(case, index, concept_texts, adjudicator, thresholds)

    def prompt_route(case: MaintenanceCase) -> tuple[str, str | None]:
        decision = prompt_only.route(case.title, case.body)
        return decision.action, decision.concept_id

    return (
        _score_maintenance("kosha_loop", cases, loop_route),
        _score_maintenance("prompt_only", cases, prompt_route),
    )


def _loop_decision(
    case: MaintenanceCase,
    index: EmbeddingIndex,
    concept_texts: dict[str, str],
    adjudicator: Adjudicator,
    thresholds: Thresholds,
) -> tuple[str, str | None]:
    draft = ConceptDraft(
        title=case.title,
        body=case.body,
        description="",
        type="concept",
        source_id=f"rw://{case.id}",
    )
    try:
        decision = resolve_draft(
            draft, index, concept_texts, adjudicator=adjudicator, thresholds=thresholds
        )
    except ValueError:
        # An unparseable adjudication is a loop failure; score it as a wrong route.
        return "SPLIT", None
    if decision.action is Action.UPDATE:
        return "UPDATE", decision.concept_id
    if decision.action is Action.CREATE:
        return "CREATE", None
    return "SPLIT", None


def _score_maintenance(
    name: str,
    cases: tuple[MaintenanceCase, ...],
    route: _RouteFn,
) -> MaintenanceResult:
    correct = 0
    kind_correct: dict[str, int] = {}
    kind_total: dict[str, int] = {}
    for case in cases:
        action, concept_id = route(case)
        ok = _is_correct(case, action, concept_id)
        correct += int(ok)
        kind_total[case.kind] = kind_total.get(case.kind, 0) + 1
        kind_correct[case.kind] = kind_correct.get(case.kind, 0) + int(ok)
    by_kind = {
        kind: kind_correct[kind] / kind_total[kind] for kind in sorted(kind_total)
    }
    return MaintenanceResult(name=name, correct=correct, total=len(cases), by_kind=by_kind)


def _is_correct(case: MaintenanceCase, action: str, concept_id: str | None) -> bool:
    if case.expected_action == "UPDATE":
        return action == "UPDATE" and concept_id == case.target
    return action == "CREATE"


def _run_drift(
    bundle: Bundle,
    embedding_provider: EmbeddingProvider,
    generation_provider: GenerationProvider,
    cases: tuple[MaintenanceCase, ...],
    config: RealworldConfig,
    adjudicator: Adjudicator,
    thresholds: Thresholds,
    work_dir: Path | None,
) -> DriftResult:
    if work_dir is None:
        with tempfile.TemporaryDirectory() as scratch:
            return _drift(
                Path(scratch), bundle, embedding_provider, generation_provider, cases, config,
                adjudicator, thresholds,
            )
    return _drift(
        work_dir, bundle, embedding_provider, generation_provider, cases, config,
        adjudicator, thresholds,
    )


def _drift(
    root: Path,
    bundle: Bundle,
    embedding_provider: EmbeddingProvider,
    generation_provider: GenerationProvider,
    cases: tuple[MaintenanceCase, ...],
    config: RealworldConfig,
    adjudicator: Adjudicator,
    thresholds: Thresholds,
) -> DriftResult:
    from kosha.git_store import GitStore

    bundle_root = root / "bundle"
    store = GitStore.init(bundle_root)
    seed_paths = _seed_bundle(bundle, bundle_root, config, cases)
    store.commit(seed_paths, "seed corpus")

    accuracy_start = _drift_accuracy(
        bundle_root, embedding_provider, adjudicator, thresholds, cases
    )
    start = datetime(2026, 1, 1, tzinfo=UTC)
    for i in range(config.ingests):
        source_dir = root / "sources" / f"ingest-{i:03d}"
        source_dir.mkdir(parents=True, exist_ok=True)
        (source_dir / "doc.md").write_text(_growth_doc(i), encoding="utf-8")
        ingest(
            source_dir,
            bundle_root,
            asof=start + timedelta(days=i + 1),
            assume_yes=True,
            git_store=store,
            embedding_provider=embedding_provider,
            generation_provider=generation_provider,
        )
    accuracy_end = _drift_accuracy(
        bundle_root, embedding_provider, adjudicator, thresholds, cases
    )
    fidelity = measure_fidelity(root / "fidelity-scratch", ingests=max(config.ingests, MIN_INGESTS))
    return DriftResult(
        ingests=config.ingests,
        accuracy_start=accuracy_start,
        accuracy_end=accuracy_end,
        fidelity_ok=fidelity.ok,
    )


def _seed_bundle(
    bundle: Bundle, bundle_root: Path, config: RealworldConfig, cases: tuple[MaintenanceCase, ...]
) -> list[Path]:
    """Write a deterministic subset of the corpus that includes every UPDATE target."""
    targets = {case.target for case in cases if case.target is not None}
    ordered = sorted(bundle.concepts)
    chosen = list(targets) + [cid for cid in ordered if cid not in targets]
    keep = sorted(set(chosen[: max(config.drift_seed_concepts, len(targets))]))
    written: list[Path] = []
    for concept_id in keep:
        path = bundle_root / f"{concept_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        source = config.corpus / f"{concept_id}.md"
        path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        written.append(path)
    return written


def _drift_accuracy(
    bundle_root: Path,
    embedding_provider: EmbeddingProvider,
    adjudicator: Adjudicator,
    thresholds: Thresholds,
    cases: tuple[MaintenanceCase, ...],
) -> float:
    bundle = load_bundle(bundle_root)
    index = EmbeddingIndex.build(bundle, embedding_provider)
    concept_texts = {cid: index_text(concept) for cid, concept in bundle.concepts.items()}
    correct = 0
    for case in cases:
        action, concept_id = _loop_decision(case, index, concept_texts, adjudicator, thresholds)
        correct += int(_is_correct(case, action, concept_id))
    return correct / len(cases) if cases else 0.0


def _growth_doc(i: int) -> str:
    return (
        f"# Synthetic topic {i}\n\n"
        f"This is benchmark growth document number {i}, describing synthetic topic "
        f"{i} that is unrelated to any existing concept so the corpus grows by one "
        f"new concept per ingest.\n"
    )


def render_realworld_report(report: RealworldReport) -> str:
    """Render ACCEPTANCE_REPORT.md: the three-way table, drift, and the verdict."""
    lines = [
        "# Kosha Real-Model Acceptance Report (M13, Gate 0)",
        "",
        f"**Verdict: {report.verdict}** "
        + (
            "- the maintenance loop beats the prompt-only baseline with real models; "
            "proceed past Gate 0."
            if report.verdict == "GO"
            else "- the loop does not clear the kill criterion; ship Kosha as an OSS "
            "skill and halt M14+."
        ),
        "",
        "## Setup",
        "",
        f"- Corpus: `{report.corpus_path}` ({report.concept_count} concepts, external)",
        f"- Embedding provider: `{report.embedding_provider}`",
        f"- Generation provider: `{report.generation_provider}`",
        f"- Held-out queries: {report.query_count}",
        "",
        "## Kill criterion (fixed before the run)",
        "",
        KILL_CRITERION,
        "",
        "## Retrieval / answer quality (held-out queries)",
        "",
        "| Strategy | Concept recall | Answer-keyword recall | Avg context tokens "
        "| Avg total tokens |",
        "|---|---|---|---|---|",
    ]
    label = {"kosha_hybrid": "kosha-loop", "tuned_rag": "tuned-rag", "prompt_only": "prompt-only"}
    for result in report.queries:
        lines.append(
            f"| {label.get(result.name, result.name)} | {result.concept_recall:.2f} | "
            f"{result.keyword_recall:.2f} | {result.avg_context_tokens:.0f} | "
            f"{result.avg_total_tokens:.0f} |"
        )
    lines.extend(
        [
            "",
            "## Maintenance quality (held-out dedup / novel / contradiction)",
            "",
            "| Decider | Accuracy | duplicate | novel | contradiction |",
            "|---|---|---|---|---|",
        ]
    )
    decider_label = {"kosha_loop": "kosha-loop", "prompt_only": "prompt-only"}
    for maint in report.maintenance:
        lines.append(
            f"| {decider_label.get(maint.name, maint.name)} | "
            f"{maint.accuracy:.2f} ({maint.correct}/{maint.total}) | "
            f"{maint.by_kind.get('duplicate', 0.0):.2f} | "
            f"{maint.by_kind.get('novel', 0.0):.2f} | "
            f"{maint.by_kind.get('contradiction', 0.0):.2f} |"
        )
    lines.extend(
        [
            "",
            f"Loop minus prompt-only maintenance accuracy: "
            f"{report.maintenance_delta:+.2f} (notable margin {NOTABLE_MARGIN:.2f}).",
            "",
            "## Drift across sequential ingests",
            "",
            f"- Ingests: {report.drift.ingests}",
            f"- Maintenance accuracy before growth: {report.drift.accuracy_start:.2f}",
            f"- Maintenance accuracy after growth: {report.drift.accuracy_end:.2f}",
            f"- Edit-drift fidelity held: {report.drift.fidelity_ok}",
            "",
            "## Decision",
            "",
            *_decision_lines(report),
            "",
        ]
    )
    return "\n".join(lines)


def _decision_lines(report: RealworldReport) -> list[str]:
    wins: list[str] = []
    losses: list[str] = []
    bucket = wins if report.beats_prompt_only else losses
    bucket.append(
        f"maintenance accuracy delta vs prompt-only is {report.maintenance_delta:+.2f}"
    )
    (wins if report.no_degradation else losses).append(
        f"maintenance accuracy moved {report.drift.accuracy_start:.2f} -> "
        f"{report.drift.accuracy_end:.2f} across {report.drift.ingests} ingests "
        f"(fidelity held: {report.drift.fidelity_ok})"
    )
    lines = [f"**Verdict: {report.verdict}.**", ""]
    lines.append("Wins:")
    lines.extend([f"- {win}" for win in wins] if wins else ["- none"])
    lines.append("")
    lines.append("Losses:")
    lines.extend([f"- {loss}" for loss in losses] if losses else ["- none"])
    return lines
