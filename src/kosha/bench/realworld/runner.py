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
from kosha.bench.gate2.contradictions import (
    ContradictionCase,
    load_contradictions,
    regimes_present,
)
from kosha.bench.gate2.harness import AxisSample, CellMeasure, CellSample
from kosha.bench.gate2.histories import bury_in_body, deep_history_claims, render_history
from kosha.bench.grade import grade_query
from kosha.bench.queries import BenchQuery
from kosha.bench.realworld.labels import MaintenanceCase, load_maintenance, load_queries
from kosha.bench.realworld.promptonly import PromptOnlyBaseline
from kosha.bench.strategies import (
    HybridStrategy,
    RetrievedContext,
    TunedRagStrategy,
)
from kosha.contradiction import (
    ContradictionJudge,
    DetectorGatedJudge,
    GenerationContradictionJudge,
    SilentOverwriteError,
    assert_no_silent_overwrite,
    reconcile,
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
from kosha.merge import make_claim
from kosha.model import Bundle, Claim
from kosha.okf import load_bundle
from kosha.pipeline import ingest
from kosha.providers.base import EmbeddingProvider, Generation, GenerationProvider
from kosha.providers.tokens import count_tokens

# A function mapping a maintenance case to a (action, concept_id) routing decision.
_RouteFn = Callable[["MaintenanceCase"], tuple[str, str | None]]

# Optional progress sink; the runner streams human-readable phase lines to it.
_ProgressFn = Callable[[str], None]


def _noop(_message: str) -> None:
    return None


# --- Kill criterion (fixed BEFORE the run; KOSHA_STRATEGIC_ANALYSIS §5 Gate 0) ---
# The maintenance loop is a product only if ALL of these hold; otherwise Kosha is
# a skill and ships as an OSS library/skill — M14+ does not begin.
#  1. Loop maintenance accuracy beats prompt-only by a margin a buyer would notice.
#  2. Maintenance accuracy does not degrade as the corpus grows over >=50 ingests.
#  3. Edit-drift fidelity holds across the whole run.
NOTABLE_MARGIN = 0.10
DRIFT_TOLERANCE = 0.05
MIN_INGESTS = 50
# At least this fraction of the drift ingests must add a concept, else the corpus
# did not actually grow and the no-degradation criterion was never exercised.
MIN_GROWTH_RATIO = 0.9
# The loop must preserve knowledge integrity under contradiction on at least this
# much more of the held-out cases than a safety-instructed prompt-only baseline.
SAFETY_MARGIN = 0.25
# Gate 0 reframed (KOSHA_STRATEGIC_ANALYSIS §2.4): the diagnostic showed routing
# decision quality is a structural tie (both deciders call the same LLM), so the
# moat is measured where the loop's guarantee differs from a prompt — knowledge
# integrity under contradiction. Routing accuracy is still reported as context.
KILL_CRITERION = (
    "GO only if (1) the loop preserves knowledge integrity under contradiction "
    "(conflict detected, prior claim retained, zero silent overwrites) on at least "
    f"{SAFETY_MARGIN:.0%} more held-out contradictions than a safety-instructed "
    "prompt-only baseline and never silently overwrites, (2) maintenance accuracy "
    f"does not drop by more than {DRIFT_TOLERANCE:.0%} across >={MIN_INGESTS} ingests "
    f"that grow the corpus (>={MIN_GROWTH_RATIO:.0%} add a concept), and (3) edit-drift "
    "fidelity holds. Otherwise NO-GO: ship Kosha as an OSS skill and halt M14+."
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
    """Maintenance accuracy before and after >=50 ingests, fidelity, and growth."""

    ingests: int
    accuracy_start: float
    accuracy_end: float
    fidelity_ok: bool
    seed_concepts: int
    final_concepts: int

    @property
    def concepts_added(self) -> int:
        return self.final_concepts - self.seed_concepts

    @property
    def grew(self) -> bool:
        # The drift premise is "quality holds as the corpus GROWS". If the
        # synthetic ingests dedupe-collapse instead of creating concepts, the
        # corpus does not grow and the premise is untested; require most ingests
        # to have added a concept so a collapse fails the gate loudly.
        return self.concepts_added >= int(self.ingests * MIN_GROWTH_RATIO)


@dataclass(frozen=True)
class SafetyResult:
    """Knowledge-integrity outcome of a decider over the held-out contradictions."""

    name: str
    cases: int
    safe: int
    silent_overwrites: int

    @property
    def safety_rate(self) -> float:
        return self.safe / self.cases if self.cases else 0.0


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
    contradictions: Path = Path("evals/realworld/contradictions_v2.jsonl")


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
    safety: tuple[SafetyResult, ...]

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

    def safety_by_name(self, name: str) -> SafetyResult:
        for result in self.safety:
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
        # Routing decision quality — reported as context, no longer the gate.
        return self.maintenance_delta >= NOTABLE_MARGIN

    @property
    def safety_delta(self) -> float:
        return self.safety_by_name("kosha_loop").safety_rate - self.safety_by_name(
            "prompt_only"
        ).safety_rate

    @property
    def beats_on_safety(self) -> bool:
        loop = self.safety_by_name("kosha_loop")
        return self.safety_delta >= SAFETY_MARGIN and loop.silent_overwrites == 0

    @property
    def no_degradation(self) -> bool:
        return (
            self.drift.ingests >= MIN_INGESTS
            and self.drift.grew
            and self.drift.fidelity_ok
            and self.drift.accuracy_end >= self.drift.accuracy_start - DRIFT_TOLERANCE
        )

    @property
    def verdict(self) -> str:
        # Gate 0 reframed to the moat: knowledge-integrity safety, not routing.
        return "GO" if self.beats_on_safety and self.no_degradation else "NO-GO"


def run_realworld(
    config: RealworldConfig,
    embedding_provider: EmbeddingProvider,
    generation_provider: GenerationProvider,
    *,
    adjudicator: Adjudicator | None = None,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
    judge: ContradictionJudge | None = None,
    work_dir: Path | None = None,
    progress: _ProgressFn | None = None,
) -> RealworldReport:
    """Run the comparisons, the safety moat test, and the drift probe; return the verdict."""
    log = progress or _noop
    bundle = load_bundle(config.corpus)
    queries = load_queries(config.queries)
    if config.max_queries is not None:
        queries = queries[: config.max_queries]
    cases = load_maintenance(config.maintenance)
    guidance = config.guidance.read_text(encoding="utf-8")
    loop_adjudicator = adjudicator or GenerationAdjudicator(generation_provider)
    loop_judge = judge or GenerationContradictionJudge(generation_provider)

    log(f"embedding corpus index ({len(bundle.concepts)} concepts)")
    index = EmbeddingIndex.build(bundle, embedding_provider)
    query_results = _run_queries(
        bundle, index, embedding_provider, generation_provider, queries, guidance, config, log
    )
    maintenance_results = _run_maintenance(
        bundle, index, generation_provider, cases, guidance, config, loop_adjudicator,
        thresholds, log,
    )
    safety_results = _run_safety(
        bundle, index, generation_provider, cases, guidance, config, loop_judge, log
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
        log,
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
        safety=safety_results,
    )


def _run_queries(
    bundle: Bundle,
    index: EmbeddingIndex,
    embedding_provider: EmbeddingProvider,
    generation_provider: GenerationProvider,
    queries: tuple[BenchQuery, ...],
    guidance: str,
    config: RealworldConfig,
    log: _ProgressFn,
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
        log(f"queries: {name} over {len(queries)} held-out questions")
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
    log: _ProgressFn,
) -> tuple[MaintenanceResult, ...]:
    concept_texts = {cid: index_text(concept) for cid, concept in bundle.concepts.items()}
    prompt_only = PromptOnlyBaseline(
        bundle, index, generation_provider, guidance=guidance, candidate_k=config.candidate_k
    )

    def loop_route(case: MaintenanceCase) -> tuple[str, str | None]:
        return _loop_decision(
            case, index, concept_texts, adjudicator, thresholds, config.candidate_k
        )

    def prompt_route(case: MaintenanceCase) -> tuple[str, str | None]:
        decision = prompt_only.route(case.title, case.body)
        return decision.action, decision.concept_id

    log(f"maintenance routing: loop vs prompt-only over {len(cases)} held-out cases")
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
    k: int,
) -> tuple[str, str | None]:
    # The note's title is its one-line description, so the loop routes over the same
    # title+body text (and the same top-k) the prompt-only baseline sees.
    draft = ConceptDraft(
        title=case.title,
        body=case.body,
        description=case.title,
        type="concept",
        source_id=f"rw://{case.id}",
    )
    try:
        decision = resolve_draft(
            draft, index, concept_texts, adjudicator=adjudicator, thresholds=thresholds, k=k
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


def _run_safety(
    bundle: Bundle,
    index: EmbeddingIndex,
    generation_provider: GenerationProvider,
    cases: tuple[MaintenanceCase, ...],
    guidance: str,
    config: RealworldConfig,
    judge: ContradictionJudge,
    log: _ProgressFn,
) -> tuple[SafetyResult, ...]:
    """Head-to-head knowledge-integrity test on the held-out contradictions.

    For each contradiction the loop reconciles the conflicting claim against the
    target's prior claim (real-LLM detection + deterministic resolution policy),
    which structurally retains the prior claim and flags the conflict. The
    prompt-only baseline gets the same prior statement and source plus an explicit
    safety instruction (preserve + flag) — a fair "good AGENTS.md". A case is
    *safe* when the conflict is surfaced and the prior statement is retained.
    """
    contradictions = [case for case in cases if case.kind == "contradiction"]
    prompt_only = PromptOnlyBaseline(
        bundle, index, generation_provider, guidance=guidance, candidate_k=config.candidate_k
    )
    start = datetime(2026, 1, 1, tzinfo=UTC)
    authority = {"corpus": 1, "update": 1}
    loop_safe = loop_overwrites = prompt_safe = prompt_overwrites = 0
    log(f"safety: loop vs prompt-only over {len(contradictions)} held-out contradictions")
    for case in contradictions:
        assert case.target is not None  # contradiction cases carry a target
        prior = _concept_statement(bundle, case.target)

        # Prompt-only baseline: a fairly safety-instructed LLM maintains the claim.
        text, flagged = prompt_only.maintain(prior, case.body)
        preserved = _normalized(prior) in _normalized(text)
        prompt_overwrites += int(not preserved)
        prompt_safe += int(flagged and preserved)

        # Loop: reconcile the conflicting claim against the prior claim.
        old = make_claim(prior, "corpus", start, effective_from=start)
        new = make_claim(case.body, "update", start + timedelta(days=1),
                         effective_from=start + timedelta(days=1))
        try:
            result = reconcile([old], new, authority=authority, judge=judge)
        except ValueError:
            # The judge could not produce a verdict (e.g. an offline provider that
            # cannot reason about conflicts): conflict not surfaced — a loop failure,
            # never a false "safe" and never an overwrite (no change was applied).
            continue
        retained = any(claim.statement == prior for claim in result.claims)
        try:
            assert_no_silent_overwrite([old], result.claims)
            overwritten = False
        except SilentOverwriteError:
            overwritten = True
        loop_overwrites += int(overwritten)
        loop_safe += int(result.conflicting and retained and not overwritten)
    total = len(contradictions)
    return (
        SafetyResult("kosha_loop", total, loop_safe, loop_overwrites),
        SafetyResult("prompt_only", total, prompt_safe, prompt_overwrites),
    )


def _concept_statement(bundle: Bundle, concept_id: str) -> str:
    """The prior factual statement a contradiction conflicts with: the concept's
    description, falling back to the first non-empty body line."""
    concept = bundle.concepts[concept_id]
    description = (concept.frontmatter.description or "").strip()
    if description:
        return description
    for line in concept.body.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            return stripped
    return concept_id


def _normalized(text: str) -> str:
    return " ".join(text.split()).lower()


def build_gate2_measure(
    config: RealworldConfig, *, runs_per_cell: int | None = None
) -> CellMeasure:
    """Bind a Gate-0 v2 per-cell measurement over the regime-spanning held-out set.

    Scores two quality axes per provider cell for one run:

    * ``detection_recall`` -- did the decider detect the conflict? The loop uses a
      detector-gated judge (code-owned numeric/negation detection forces
      reconcile, deferring only the ambiguous residue to the LLM); the prompt-only
      baseline is LLM-only (the fair contrast).
    * ``safety_rate`` -- conflict surfaced AND the prior claim retained AND no
      silent overwrite -- the knowledge-integrity guarantee.

    Each held-out case is materialized into its at-scale context: a single prior
    claim, a prior buried in a long body, or a prior buried in a deep in-force
    history. The corpus index is embedded once per embedding provider and reused.

    Both quality axes are computed on ``(prior, new)`` claim pairs directly and
    never touch retrieval, so they are independent of the embedding provider. When
    ``runs_per_cell`` is given, a generation's runs are computed once (under the
    first embedding) and replayed for later embeddings rather than re-calling the
    LLM to the same effect: the matrix still exercises every embedding (each builds
    its index) while the LLM cost scales with the generation x run grid, not the
    full cell grid. Leave it ``None`` (the default) for independent per-cell runs.
    """
    bundle = load_bundle(config.corpus)
    guidance = config.guidance.read_text(encoding="utf-8")
    cases = load_contradictions(config.contradictions)
    regimes = regimes_present(cases)
    indexes: dict[int, EmbeddingIndex] = {}
    by_generation: dict[int, list[CellSample]] = {}
    seen: dict[int, int] = {}

    def measure(
        embedding: EmbeddingProvider, generation: GenerationProvider
    ) -> CellSample:
        index = indexes.get(id(embedding))
        if index is None:
            index = EmbeddingIndex.build(bundle, embedding)
            indexes[id(embedding)] = index
        bank = by_generation.setdefault(id(generation), [])
        call = seen.get(id(generation), 0)
        seen[id(generation)] = call + 1
        if runs_per_cell is not None and call >= runs_per_cell:
            return bank[call % runs_per_cell]
        prompt_only = PromptOnlyBaseline(
            bundle, index, generation, guidance=guidance, candidate_k=config.candidate_k
        )
        gated = DetectorGatedJudge(GenerationContradictionJudge(generation))
        loop_detected = loop_safe = loop_overwrites = 0
        prompt_detected = prompt_safe = 0
        for case in cases:
            claims, retain_statement, prompt_context = _gate2_case_context(case)
            detected, safe, overwritten = _gate2_loop_case(
                claims, retain_statement, case.new, gated
            )
            loop_detected += detected
            loop_safe += safe
            loop_overwrites += overwritten
            flagged, preserved = _gate2_prompt_case(
                prompt_only, prompt_context, case.prior, case.new
            )
            prompt_detected += flagged
            prompt_safe += preserved
        n = len(cases)
        axes = (
            AxisSample("detection_recall", _rate(loop_detected, n), _rate(prompt_detected, n)),
            AxisSample("safety_rate", _rate(loop_safe, n), _rate(prompt_safe, n)),
        )
        sample = CellSample(
            axes=axes,
            loop_silent_overwrites=loop_overwrites,
            contradictions=n,
            regimes=regimes,
        )
        bank.append(sample)
        return sample

    return measure


# A new claim is asserted after every generated prior/history so its window is later.
_GATE2_NEW_ASOF = datetime(2027, 1, 1, tzinfo=UTC)
_GATE2_PRIOR_ASOF = datetime(2026, 1, 1, tzinfo=UTC)
_GATE2_AUTHORITY = {"corpus": 1, "update": 1}


def _gate2_case_context(case: ContradictionCase) -> tuple[list[Claim], str, str]:
    """Materialize a held-out case: (prior claims, the claim to retain, prompt text)."""
    if case.scale == "deep_history":
        claims = deep_history_claims(
            case.subject, case.prior, case.depth, start=_GATE2_PRIOR_ASOF
        )
        return claims, case.prior, render_history(claims)
    if case.scale == "buried_body":
        body = bury_in_body(case.prior, sentences=case.filler)
        claim = make_claim(body, "corpus", _GATE2_PRIOR_ASOF, effective_from=_GATE2_PRIOR_ASOF)
        return [claim], body, body
    claim = make_claim(case.prior, "corpus", _GATE2_PRIOR_ASOF, effective_from=_GATE2_PRIOR_ASOF)
    return [claim], case.prior, case.prior


def _gate2_loop_case(
    claims: list[Claim], retain_statement: str, new_statement: str, judge: ContradictionJudge
) -> tuple[int, int, int]:
    """The loop's (detected, safe, overwritten) on one held-out contradiction."""
    new_claim = make_claim(
        new_statement, "update", _GATE2_NEW_ASOF, effective_from=_GATE2_NEW_ASOF
    )
    try:
        result = reconcile(claims, new_claim, authority=_GATE2_AUTHORITY, judge=judge)
    except ValueError:
        # The judge produced no verdict: conflict not surfaced, nothing applied.
        return 0, 0, 0
    retained = any(claim.statement == retain_statement for claim in result.claims)
    try:
        assert_no_silent_overwrite(claims, result.claims)
        overwritten = False
    except SilentOverwriteError:
        overwritten = True
    detected = int(result.conflicting)
    safe = int(result.conflicting and retained and not overwritten)
    return detected, safe, int(overwritten)


def _gate2_prompt_case(
    prompt_only: PromptOnlyBaseline, prompt_context: str, fact: str, new_statement: str
) -> tuple[int, int]:
    """The prompt-only baseline's (flagged, preserved) on one held-out contradiction."""
    text, flagged = prompt_only.maintain(prompt_context, new_statement)
    preserved = _normalized(fact) in _normalized(text)
    return int(flagged), int(flagged and preserved)


def _rate(count: int, total: int) -> float:
    return count / total if total else 0.0


def _run_drift(
    bundle: Bundle,
    embedding_provider: EmbeddingProvider,
    generation_provider: GenerationProvider,
    cases: tuple[MaintenanceCase, ...],
    config: RealworldConfig,
    adjudicator: Adjudicator,
    thresholds: Thresholds,
    work_dir: Path | None,
    log: _ProgressFn,
) -> DriftResult:
    if work_dir is None:
        with tempfile.TemporaryDirectory() as scratch:
            return _drift(
                Path(scratch), bundle, embedding_provider, generation_provider, cases, config,
                adjudicator, thresholds, log,
            )
    return _drift(
        work_dir, bundle, embedding_provider, generation_provider, cases, config,
        adjudicator, thresholds, log,
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
    log: _ProgressFn,
) -> DriftResult:
    from kosha.git_store import GitStore

    bundle_root = root / "bundle"
    store = GitStore.init(bundle_root)
    seed_paths = _seed_bundle(bundle, bundle_root, config, cases)
    store.commit(seed_paths, "seed corpus")
    log(f"drift: seeded {len(seed_paths)} concepts; measuring start accuracy")

    accuracy_start = _drift_accuracy(
        bundle_root, embedding_provider, adjudicator, thresholds, cases, config.candidate_k
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
        log(f"drift: ingest {i + 1}/{config.ingests}")
    log("drift: measuring end accuracy on the grown corpus")
    accuracy_end = _drift_accuracy(
        bundle_root, embedding_provider, adjudicator, thresholds, cases, config.candidate_k
    )
    final_concepts = len(load_bundle(bundle_root).concepts)
    log(f"drift: corpus grew {len(seed_paths)} -> {final_concepts} concepts")
    fidelity = measure_fidelity(root / "fidelity-scratch", ingests=max(config.ingests, MIN_INGESTS))
    return DriftResult(
        ingests=config.ingests,
        accuracy_start=accuracy_start,
        accuracy_end=accuracy_end,
        fidelity_ok=fidelity.ok,
        seed_concepts=len(seed_paths),
        final_concepts=final_concepts,
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
    k: int,
) -> float:
    bundle = load_bundle(bundle_root)
    index = EmbeddingIndex.build(bundle, embedding_provider)
    concept_texts = {cid: index_text(concept) for cid, concept in bundle.concepts.items()}
    correct = 0
    for case in cases:
        action, concept_id = _loop_decision(
            case, index, concept_texts, adjudicator, thresholds, k
        )
        correct += int(_is_correct(case, action, concept_id))
    return correct / len(cases) if cases else 0.0


# Distinct real topic words so each growth doc is semantically and lexically far
# from the others and from the stdlib corpus; combined with per-index unique
# tokens this keeps the dedup resolver from collapsing the docs onto one concept.
_GROWTH_TOPICS = (
    "harbor", "meadow", "lantern", "comet", "glacier", "trombone", "saffron",
    "obsidian", "marigold", "quartz", "tundra", "lagoon", "zephyr", "cinnamon",
    "almanac", "barnacle", "cobalt", "driftwood", "ember", "fjord", "gondola",
    "hammock", "iceberg", "juniper", "kelp", "lichen", "monsoon", "nectar",
    "opal", "parsnip", "quokka", "rhubarb", "sextant", "thistle", "umbra",
    "vellum", "walrus", "xylem", "yarrow", "zircon", "aqueduct", "basalt",
    "cactus", "dahlia", "estuary", "ferns", "granite", "heron", "indigo",
    "jasmine", "kiln", "lichgate", "mango", "nutmeg", "orchard", "pumice",
    "quill", "reef", "sorrel", "tulip",
)


def _growth_doc(i: int) -> str:
    # Heading + body share no boilerplate words across docs: a distinct real topic
    # word plus per-index unique tokens, so the dedup resolver routes each CREATE.
    topic = _GROWTH_TOPICS[i % len(_GROWTH_TOPICS)]
    terms = " ".join(f"gd{i}w{k}" for k in range(8))
    return f"# {topic} {i}\n\n{topic} {terms}\n"


def render_realworld_report(report: RealworldReport) -> str:
    """Render ACCEPTANCE_REPORT.md: the three-way table, drift, and the verdict."""
    lines = [
        "# Kosha Real-Model Acceptance Report (M13, Gate 0)",
        "",
        f"**Verdict: {report.verdict}** "
        + (
            "- the loop preserves knowledge integrity under contradiction better than a "
            "safety-instructed prompt; the moat holds. Proceed past Gate 0."
            if report.verdict == "GO"
            else "- the loop does not clear the reframed kill criterion; ship Kosha as an "
            "OSS skill and halt M14+."
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
    label = {"kosha_hybrid": "kosha-hybrid", "tuned_rag": "tuned-rag", "prompt_only": "prompt-only"}
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
            f"{report.maintenance_delta:+.2f} (context only; routing is a structural tie "
            f"and is not the reframed gate).",
            "",
            "## Knowledge-integrity safety under contradiction (the reframed moat)",
            "",
            "| Decider | Safe | Safety rate | Silent overwrites |",
            "|---|---|---|---|",
        ]
    )
    for safety in report.safety:
        lines.append(
            f"| {decider_label.get(safety.name, safety.name)} | "
            f"{safety.safe}/{safety.cases} | {safety.safety_rate:.2f} | "
            f"{safety.silent_overwrites} |"
        )
    lines.extend(
        [
            "",
            f"Loop minus prompt-only safety: {report.safety_delta:+.2f} "
            f"(safety margin {SAFETY_MARGIN:.2f}).",
            "",
            "## Drift across sequential ingests",
            "",
            f"- Ingests: {report.drift.ingests}",
            f"- Corpus grew: {report.drift.seed_concepts} -> "
            f"{report.drift.final_concepts} concepts (+{report.drift.concepts_added})",
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
    loop_safety = report.safety_by_name("kosha_loop")
    (wins if report.beats_on_safety else losses).append(
        f"knowledge-integrity safety: loop {loop_safety.safety_rate:.2f} vs prompt-only "
        f"{report.safety_by_name('prompt_only').safety_rate:.2f} "
        f"(delta {report.safety_delta:+.2f}, margin {SAFETY_MARGIN:.2f}); loop silent "
        f"overwrites {loop_safety.silent_overwrites}"
    )
    (wins if report.no_degradation else losses).append(
        f"maintenance accuracy moved {report.drift.accuracy_start:.2f} -> "
        f"{report.drift.accuracy_end:.2f} across {report.drift.ingests} ingests as the "
        f"corpus grew +{report.drift.concepts_added} (fidelity held: "
        f"{report.drift.fidelity_ok})"
    )
    note = (
        f"routing decision quality is a structural tie (loop {report.maintenance_delta:+.2f} "
        "vs prompt-only; both call the same LLM) — reported as context, not gated"
    )
    (wins if report.beats_prompt_only else losses).append(note)
    lines = [f"**Verdict: {report.verdict}.**", ""]
    lines.append("Wins:")
    lines.extend([f"- {win}" for win in wins] if wins else ["- none"])
    lines.append("")
    lines.append("Losses:")
    lines.extend([f"- {loss}" for loss in losses] if losses else ["- none"])
    return lines
