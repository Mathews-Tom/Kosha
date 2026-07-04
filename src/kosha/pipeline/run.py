"""End-to-end ingest: extract -> dedup -> merge -> link -> index/log -> plan -> commit.

:func:`ingest` wires the full maintenance loop (system_design §4.1) behind the
plan -> approve -> commit gate:

1. read the source folder into ``RawDoc``s and extract candidate concepts (M5);
2. resolve each draft to UPDATE/CREATE/SPLIT against the embedding index (M6);
3. apply through the claim layer — supersede or reconcile, never overwrite (M7/M9);
4. cross-link and regenerate ``index.md`` / append ``log.md`` (M8);
5. assemble a :class:`~kosha.plan.ChangePlan`, route it by graduated autonomy (§4.5);
6. on approval, write the files and commit them on an ingest branch (§6).

Everything before step 6 is pure: ``dry_run`` stops after step 5 with the plan, and
nothing reaches Git without an approval (delegated for auto/skim lanes, explicit for
the block lane).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from kosha.approve import (
    DEFAULT_THRESHOLDS,
    AutonomyThresholds,
    Decision,
    PlanRouting,
    Reader,
    normalize_reviewer,
    request_decision,
    route_plan,
)
from kosha.contradiction.detect import LexicalContradictionJudge
from kosha.dedup import (
    Action,
    DecisionRecord,
    LexicalAdjudicator,
    make_splitter,
    record_decisions,
    resolve_draft,
)
from kosha.dedup.resolver import Decision as DedupDecision
from kosha.dedup.split import Splitter
from kosha.extract import ConceptDraft, extract_concepts
from kosha.git_store import GitStore, IngestLock
from kosha.index.embedding import EmbeddingIndex, index_text
from kosha.indexlog import LogEntry, append_entries, regenerate_indexes
from kosha.ingest import ingest_folder
from kosha.link import LexicalRelator, compute_backlinks, crosslink
from kosha.merge.create import create_concept
from kosha.merge.update import LexicalClaimTargeter
from kosha.model import Bundle, Concept, Source
from kosha.okf.load import load_bundle
from kosha.okf.serialize import serialize_concept
from kosha.pipeline.writer import UpdateResult, apply_update, new_concept_id
from kosha.plan import (
    ChangeKind,
    ChangePlan,
    ContradictionState,
    FileChange,
    Flag,
    Impact,
    build_plan,
)
from kosha.providers import resolve_embedding_provider, resolve_generation_provider
from kosha.providers.base import EmbeddingProvider, GenerationProvider
from kosha.security.secret_scan import scan_text
from kosha.telemetry import (
    TelemetrySink,
    emit_decision,
    emit_provider_call,
    emit_route,
)

_LOG_NAME = "log.md"
# Top-level source directory -> OKF concept type, so a folder mirroring the bundle
# layout mints concepts with a sensible type; anything else is a generic concept.
_TYPE_BY_DIR = {
    "policies": "policy",
    "playbooks": "playbook",
    "entities": "entity",
    "references": "reference",
}


@dataclass(frozen=True)
class _ChangeMeta:
    """Routing provenance recorded for a concept the loop created or updated."""

    summary: str
    confidence: float
    impact: Impact
    contradiction: ContradictionState


@dataclass(frozen=True)
class _Tools:
    """The deterministic surfaces and read-only inputs the loop resolves against."""

    index: EmbeddingIndex
    concept_texts: dict[str, str]
    adjudicator: LexicalAdjudicator
    splitter: Splitter
    targeter: LexicalClaimTargeter
    judge: LexicalContradictionJudge
    authority: dict[str, int]
    asof: datetime
    reviewer: str | None = None
    telemetry_sink: TelemetrySink | None = None


@dataclass
class _Accumulator:
    """The mutable working state the loop builds up across drafts."""

    concepts: dict[str, Concept]
    meta: dict[str, _ChangeMeta] = field(default_factory=dict)
    flags: list[Flag] = field(default_factory=list)
    audit: list[DecisionRecord] = field(default_factory=list)


@dataclass
class IngestResult:
    """The outcome of an ingest run."""

    plan: ChangePlan
    routing: PlanRouting
    decision: Decision | None = None
    committed: bool = False
    branch: str | None = None
    commit_sha: str | None = None
    backup_tag: str | None = None
    reviewer: str | None = None
    audit: list[DecisionRecord] = field(default_factory=list)


def decide_plan(
    routing: PlanRouting, *, reader: Reader | None = None, assume_yes: bool = False
) -> Decision:
    """Decide whether a routed plan may apply.

    Auto/skim plans are approved under the delegated autonomy policy; a blocked
    plan needs an explicit yes — ``assume_yes`` (e.g. ``--yes``), the interactive
    ``reader``, or, with neither, a default-safe reject.
    """
    if assume_yes:
        return Decision.APPROVE
    if not routing.requires_approval:
        return Decision.APPROVE
    if reader is None:
        return Decision.REJECT
    return request_decision(reader)


def ingest(
    source: Path,
    bundle_root: Path,
    *,
    asof: datetime,
    source_authority: int = 0,
    thresholds: AutonomyThresholds = DEFAULT_THRESHOLDS,
    dry_run: bool = False,
    assume_yes: bool = False,
    reader: Reader | None = None,
    git_store: GitStore | None = None,
    branch: str | None = None,
    reviewer: str | None = None,
    embedding_provider: EmbeddingProvider | None = None,
    generation_provider: GenerationProvider | None = None,
    telemetry_sink: TelemetrySink | None = None,
) -> IngestResult:
    """Ingest ``source`` into the bundle at ``bundle_root`` behind the approve gate.

    ``reviewer`` is the approving human's identity (e.g. "Jane Doe
    <jane@example.com>"); when supplied it is recorded as a ``Reviewed-by``
    trailer on the commit. It is normalized (and validated) up front so a
    malformed value fails before any pipeline work runs, not after.
    """
    reviewer = normalize_reviewer(reviewer)
    embedder = embedding_provider or resolve_embedding_provider()
    generator = generation_provider or resolve_generation_provider()

    raw_docs = ingest_folder(source, authority_rank=source_authority)
    bundle = (
        load_bundle(bundle_root) if bundle_root.is_dir() else Bundle(root_path=str(bundle_root))
    )
    index = EmbeddingIndex.build(bundle, embedder)
    tools = _Tools(
        index=index,
        concept_texts={cid: index_text(c) for cid, c in bundle.concepts.items()},
        adjudicator=LexicalAdjudicator(),
        splitter=make_splitter(generator),
        targeter=LexicalClaimTargeter(),
        judge=LexicalContradictionJudge(),
        authority={raw.source.source_id: raw.source.authority_rank for raw in raw_docs},
        asof=asof,
        reviewer=reviewer,
        telemetry_sink=telemetry_sink,
    )
    accum = _Accumulator(concepts=dict(bundle.concepts))

    emit_provider_call(
        telemetry_sink,
        surface="pipeline.extract",
        provider_name=generator.name,
    )
    for raw in raw_docs:
        type_hint = _TYPE_BY_DIR.get(_top_dir(raw.source.source_id), "concept")
        for draft in extract_concepts(raw, generator, type_hint=type_hint):
            _resolve_and_apply(draft, raw.source, tools, accum)

    linked = crosslink(bundle.model_copy(update={"concepts": accum.concepts}), LexicalRelator())
    changes = _scan_secrets(
        [
            *_concept_changes(bundle, linked, accum.meta),
            *_index_changes(bundle_root, linked),
            *_log_change(bundle_root, accum.meta, asof),
        ]
    )
    plan = build_plan(changes, accum.flags)
    routing = route_plan(plan, thresholds)
    for route in routing.routes:
        emit_route(
            telemetry_sink,
            surface="pipeline.route",
            lane=route.lane.label,
            confidence=route.change.confidence,
            provider_name=embedder.name,
        )
    if dry_run:
        return IngestResult(plan, routing, audit=accum.audit)

    decision = decide_plan(routing, reader=reader, assume_yes=assume_yes)
    emit_decision(
        telemetry_sink,
        surface="pipeline.approve",
        outcome=decision.value,
        lane=routing.lane.label,
    )
    result = IngestResult(plan, routing, decision=decision, reviewer=reviewer, audit=accum.audit)
    if decision is Decision.APPROVE and not plan.is_empty:
        _commit(plan, bundle_root, asof, source, git_store, branch, reviewer, result)
    return result


def _resolve_and_apply(
    draft: ConceptDraft, source: Source, tools: _Tools, accum: _Accumulator
) -> None:
    """Resolve one draft and apply it; a SPLIT re-segments and re-resolves each part."""
    decision = resolve_draft(draft, tools.index, tools.concept_texts, adjudicator=tools.adjudicator)
    accum.audit.extend(record_decisions(draft, decision))
    if decision.action is Action.SPLIT:
        for sub_draft in tools.splitter(draft):
            _resolve_and_apply(sub_draft, source, tools, accum)
        return
    _apply(decision, draft, source, tools, accum)


def _apply(
    decision: DedupDecision,
    draft: ConceptDraft,
    source: Source,
    tools: _Tools,
    accum: _Accumulator,
) -> None:
    """Apply a terminal UPDATE/CREATE decision to the working concept set."""
    confidence = 0.5 if decision.adjudicated else 1.0
    emit_decision(
        tools.telemetry_sink,
        surface="pipeline.dedup",
        outcome=decision.action.value,
        confidence=confidence,
        provider_name=tools.adjudicator.__class__.__name__,
    )
    if decision.action is Action.UPDATE:
        assert decision.concept_id is not None
        existing = accum.concepts[decision.concept_id]
        result = apply_update(
            existing,
            draft,
            source,
            tools.asof,
            authority=tools.authority,
            targeter=tools.targeter,
            judge=tools.judge,
            reviewer=tools.reviewer,
        )
        accum.concepts[decision.concept_id] = result.concept
        accum.meta[decision.concept_id] = _ChangeMeta(
            summary=_update_summary(result),
            confidence=confidence,
            impact=Impact.MEDIUM if result.superseded else Impact.LOW,
            contradiction=result.contradiction,
        )
        accum.flags.extend(
            Flag(
                concept_id=decision.concept_id,
                summary=f"contradiction: {escalation.rationale}",
                detail=f"new: {escalation.new_claim.statement}",
            )
            for escalation in result.escalations
        )
    elif decision.action is Action.CREATE:
        concept_id = new_concept_id(draft, source, taken=set(accum.concepts))
        accum.concepts[concept_id] = create_concept(
            draft, concept_id, source, tools.asof, reviewer=tools.reviewer
        )
        accum.meta[concept_id] = _ChangeMeta(
            summary=f"new {accum.concepts[concept_id].frontmatter.type}: {draft.title}",
            confidence=confidence,
            impact=Impact.LOW,
            contradiction=ContradictionState.NONE,
        )


def _concept_changes(
    original: Bundle, linked: Bundle, meta: dict[str, _ChangeMeta]
) -> list[FileChange]:
    """Emit a change per new/updated/relinked concept; skip untouched ones."""
    before_backlinks = compute_backlinks(original)
    after_backlinks = compute_backlinks(linked)
    changes: list[FileChange] = []
    for concept_id, concept in linked.concepts.items():
        existing = original.concepts.get(concept_id)
        is_new = existing is None
        links_changed = existing is not None and (
            concept.out_links != existing.out_links
            or after_backlinks.get(concept_id, []) != before_backlinks.get(concept_id, [])
        )
        if not (is_new or concept_id in meta or links_changed):
            continue
        content = serialize_concept(concept)
        if existing is not None and content == serialize_concept(existing):
            continue
        info = meta.get(concept_id)
        changes.append(
            FileChange(
                path=f"{concept_id}.md",
                kind=ChangeKind.CREATE if is_new else ChangeKind.UPDATE,
                content=content,
                concept_id=concept_id,
                summary=info.summary if info else "cross-link update",
                confidence=info.confidence if info else 1.0,
                impact=info.impact if info else Impact.LOW,
                contradiction=info.contradiction if info else ContradictionState.NONE,
            )
        )
    return changes


def _scan_secrets(changes: list[FileChange]) -> list[FileChange]:
    """Flag any change whose content matches a secret-like pattern.

    A flagged change forces its own BLOCK routing (see route_change), so a
    secret-like write requires explicit human approval rather than
    auto-applying on the ingest branch.
    """
    scanned: list[FileChange] = []
    for change in changes:
        detectors = scan_text(change.content)
        scanned.append(
            change.model_copy(update={"secret_detectors": detectors}) if detectors else change
        )
    return scanned


def _index_changes(bundle_root: Path, linked: Bundle) -> list[FileChange]:
    """Emit a change per regenerated ``index.md`` whose content moved."""
    changes: list[FileChange] = []
    for rel_path, content in regenerate_indexes(linked).items():
        on_disk = bundle_root / rel_path
        if on_disk.is_file() and on_disk.read_text(encoding="utf-8") == content:
            continue
        kind = ChangeKind.UPDATE if on_disk.is_file() else ChangeKind.CREATE
        changes.append(
            FileChange(path=rel_path, kind=kind, content=content, summary="regenerate index")
        )
    return changes


def _log_change(
    bundle_root: Path, meta: dict[str, _ChangeMeta], asof: datetime
) -> list[FileChange]:
    """Append a dated log entry per create/update; no entries means no change."""
    entries = [
        LogEntry(on=asof.date(), kind=_log_kind(info), summary=info.summary)
        for info in (meta[cid] for cid in sorted(meta))
    ]
    if not entries:
        return []
    log_path = bundle_root / _LOG_NAME
    existing = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""
    content = append_entries(existing, entries)
    kind = ChangeKind.UPDATE if log_path.is_file() else ChangeKind.CREATE
    return [FileChange(path=_LOG_NAME, kind=kind, content=content, summary="append change log")]


def _commit(
    plan: ChangePlan,
    bundle_root: Path,
    asof: datetime,
    source: Path,
    git_store: GitStore | None,
    branch: str | None,
    reviewer: str | None,
    result: IngestResult,
) -> None:
    """Write the approved plan and commit it on an ingest branch with a backup tag.

    The branch-switch/write/commit sequence mutates the repo's one shared
    working tree, so it runs under an exclusive per-repository lock: a second
    concurrent ingest against the same bundle fails loudly (IngestLockError)
    rather than racing this one's branch switch or file writes. When a
    reviewer identity was supplied and approved the plan, it is recorded as a
    ``Reviewed-by`` trailer so the commit names who approved it.
    """
    store = git_store or GitStore(bundle_root)
    with IngestLock(store.repo):
        branch_name = branch or f"ingest/{source.name}-{asof:%Y%m%d%H%M%S}"
        store.create_branch(branch_name)
        written: list[Path] = []
        for change in plan.changes:
            path = bundle_root / change.path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(change.content, encoding="utf-8")
            written.append(path)
        body = "\n".join(f"- {change.kind.value} {change.path}" for change in plan.changes)
        message = f"feat(kosha): ingest {source.name}\n\n{body}"
        if reviewer is not None:
            message = f"{message}\n\nReviewed-by: {reviewer}"
        result.commit_sha = store.commit(written, message)
        result.backup_tag = store.tag_daily_backup(asof.date())
        result.committed = True
        result.branch = branch_name


def _update_summary(result: UpdateResult) -> str:
    if result.contradiction is ContradictionState.ESCALATED:
        return f"update {result.concept.concept_id} (contradiction escalated)"
    if result.superseded:
        return f"update {result.concept.concept_id} (supersede)"
    return f"update {result.concept.concept_id}"


def _log_kind(info: _ChangeMeta) -> str:
    if info.contradiction is not ContradictionState.NONE:
        return "conflict"
    return info.impact.value


def _top_dir(rel_path: str) -> str:
    head, _, tail = rel_path.partition("/")
    return head if tail else ""
