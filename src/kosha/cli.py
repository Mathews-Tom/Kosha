"""Command-line entrypoint for Kosha.

``--version`` prints the package version and a bare invocation prints help.
``kosha validate <bundle>`` checks an OKF bundle for v0.1 conformance and exits
non-zero when the bundle has conformance errors; warnings (broken links,
granularity) are reported but never change a conformant exit code.
``kosha bench`` runs the Premise-Validation benchmark over a golden bundle,
printing the hybrid/RAG/long-context comparison table and optionally writing a
report.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path

from kosha import __version__
from kosha.approve import render_plan, render_routing
from kosha.bench import (
    calibrate_thresholds,
    default_threshold_mismatch,
    evaluate_granularity,
    evaluate_kill_signals,
    evaluate_threshold_only,
    go_no_go,
    load_dedup_pairs,
    load_granularity_labels,
    render_calibration,
    render_premise_report,
    render_table,
    run_benchmark,
)
from kosha.bench.acceptance import render_acceptance_report, run_acceptance
from kosha.bench.corpus import CORPUS_NAME, build_corpus
from kosha.bench.gate2 import MIN_RUNS as GATE2_MIN_RUNS
from kosha.bench.gate2 import Gate2Criterion, run_gate2
from kosha.bench.gate2.auditability import run_auditability
from kosha.bench.gate2.contradictions import load_contradictions
from kosha.bench.gate2.report import render_gate2_report
from kosha.bench.realworld import (
    RealworldConfig,
    build_gate2_measure,
    render_realworld_report,
    run_realworld,
)
from kosha.contradiction import LexicalContradictionJudge
from kosha.dedup import DEFAULT_THRESHOLDS, LexicalAdjudicator
from kosha.eval import (
    evaluate_contradict,
    evaluate_dedup,
    evaluate_duplicate_rate,
    evaluate_extractor,
    evaluate_merge,
    evaluate_relate,
    load_contradict_cases,
    load_merge_cases,
    load_relate_cases,
)
from kosha.link import LexicalRelator
from kosha.merge import LexicalClaimTargeter
from kosha.okf import load_bundle
from kosha.pipeline import ingest
from kosha.providers import resolve_embedding_provider, resolve_generation_provider
from kosha.providers.matrix import resolve_provider_matrix
from kosha.validate import validate_bundle

# Default golden corpus the benchmark runs against, and the seed label files.
_DEFAULT_BUNDLE = Path("bundles/northwind")
_DEDUP_LABELS = Path("labels/dedup_seed.jsonl")
_GRANULARITY_LABELS = Path("labels/granularity_seed.jsonl")
_MERGE_LABELS = Path("labels/merge_seed.jsonl")
_RELATE_LABELS = Path("labels/relate_seed.jsonl")
_CONTRADICT_LABELS = Path("labels/contradict_seed.jsonl")


def build_parser() -> argparse.ArgumentParser:
    """Construct the root argument parser."""
    parser = argparse.ArgumentParser(
        prog="kosha",
        description="Self-maintaining OKF knowledge engine.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command")
    validate_parser = subparsers.add_parser(
        "validate",
        help="Check an OKF bundle for v0.1 conformance.",
    )
    validate_parser.add_argument(
        "bundle",
        type=Path,
        help="Path to the OKF bundle directory.",
    )
    bench_parser = subparsers.add_parser(
        "bench",
        help="Run the Premise-Validation retrieval benchmark.",
    )
    bench_parser.add_argument(
        "--bundle",
        type=Path,
        default=_DEFAULT_BUNDLE,
        help="Golden bundle to benchmark (default: bundles/northwind).",
    )
    bench_parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Write the benchmark report to this path.",
    )
    bench_subparsers = bench_parser.add_subparsers(dest="bench_command")
    acceptance_parser = bench_subparsers.add_parser(
        "acceptance",
        help="Gate the MVP success criteria on the golden corpus (exit 0 iff all pass).",
    )
    acceptance_parser.add_argument(
        "--bundle",
        type=Path,
        default=_DEFAULT_BUNDLE,
        help="Golden bundle to gate (default: bundles/northwind).",
    )
    acceptance_parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Write the acceptance report to this path.",
    )
    corpus_parser = bench_subparsers.add_parser(
        "corpus",
        help="Regenerate the external stdlib benchmark corpus (DEVELOPMENT_PLAN M13).",
    )
    corpus_parser.add_argument(
        "--out",
        type=Path,
        default=Path(f"bundles/{CORPUS_NAME}"),
        help=f"Output bundle directory (default: bundles/{CORPUS_NAME}).",
    )
    realworld_parser = bench_subparsers.add_parser(
        "realworld",
        help="Run the M13 real-model, held-out benchmark and record the go/no-go verdict.",
    )
    realworld_parser.add_argument(
        "--corpus",
        type=Path,
        default=Path(f"bundles/{CORPUS_NAME}"),
        help=f"External corpus bundle (default: bundles/{CORPUS_NAME}).",
    )
    realworld_parser.add_argument(
        "--queries",
        type=Path,
        default=Path("evals/realworld/queries.jsonl"),
        help="Held-out query set (default: evals/realworld/queries.jsonl).",
    )
    realworld_parser.add_argument(
        "--maintenance",
        type=Path,
        default=Path("evals/realworld/maintenance.jsonl"),
        help="Held-out maintenance cases (default: evals/realworld/maintenance.jsonl).",
    )
    realworld_parser.add_argument(
        "--guidance",
        type=Path,
        default=Path("consumer/AGENTS.fragment.md"),
        help="AGENTS fragment given to the prompt-only baseline.",
    )
    realworld_parser.add_argument(
        "--ingests",
        type=int,
        default=50,
        help="Sequential ingests in the drift probe (default: 50).",
    )
    realworld_parser.add_argument(
        "--seed-concepts",
        type=int,
        default=150,
        help="Corpus concepts seeded into the drift bundle (default: 150).",
    )
    realworld_parser.add_argument(
        "--max-queries",
        type=int,
        default=None,
        help="Cap the held-out queries evaluated (default: all).",
    )
    realworld_parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Write the acceptance report to this path.",
    )
    realworld_parser.add_argument(
        "--gate2",
        action="store_true",
        help="Run the pre-registered Gate-0 v2 re-test across the provider matrix.",
    )
    realworld_parser.add_argument(
        "--contradictions",
        type=Path,
        default=Path("evals/realworld/contradictions_v2.jsonl"),
        help="Held-out Gate-0 v2 contradiction set "
        "(default: evals/realworld/contradictions_v2.jsonl).",
    )
    realworld_parser.add_argument(
        "--runs",
        type=int,
        default=GATE2_MIN_RUNS,
        help=f"Runs per provider cell for the Gate-0 v2 distributions (default: {GATE2_MIN_RUNS}).",
    )
    calibrate_parser = subparsers.add_parser(
        "calibrate",
        help="Fit the dedup thresholds to the configured embedding on the seed labels.",
    )
    calibrate_parser.add_argument(
        "--labels",
        type=Path,
        default=_DEDUP_LABELS,
        help="Seed dedup labels to fit on (default: labels/dedup_seed.jsonl).",
    )
    calibrate_parser.add_argument(
        "--margin",
        type=float,
        default=0.02,
        help="Safety margin past the seed score extremes (default: 0.02).",
    )
    eval_parser = subparsers.add_parser(
        "eval",
        help="Run an LLM-surface eval suite.",
    )
    eval_subparsers = eval_parser.add_subparsers(dest="eval_command")
    extract_eval_parser = eval_subparsers.add_parser(
        "extract",
        help="Score the concept extractor against seed granularity labels.",
    )
    extract_eval_parser.add_argument(
        "--labels",
        type=Path,
        default=_GRANULARITY_LABELS,
        help="Granularity seed labels (default: labels/granularity_seed.jsonl).",
    )
    dedup_eval_parser = eval_subparsers.add_parser(
        "dedup",
        help="Score the dedup resolver: precision/recall + duplicate rate.",
    )
    dedup_eval_parser.add_argument(
        "--labels",
        type=Path,
        default=_DEDUP_LABELS,
        help="Dedup seed pairs (default: labels/dedup_seed.jsonl).",
    )
    dedup_eval_parser.add_argument(
        "--bundle",
        type=Path,
        default=_DEFAULT_BUNDLE,
        help="Repeated-ingest bundle for duplicate rate (default: bundles/northwind).",
    )
    merge_eval_parser = eval_subparsers.add_parser(
        "merge",
        help="Score the merge surface: claim-targeting accuracy.",
    )
    merge_eval_parser.add_argument(
        "--labels",
        type=Path,
        default=_MERGE_LABELS,
        help="Merge claim-targeting cases (default: labels/merge_seed.jsonl).",
    )
    relate_eval_parser = eval_subparsers.add_parser(
        "relate",
        help="Score the cross-linker relate surface: link-discovery precision/recall.",
    )
    relate_eval_parser.add_argument(
        "--labels",
        type=Path,
        default=_RELATE_LABELS,
        help="Relate cases (default: labels/relate_seed.jsonl).",
    )
    contradict_eval_parser = eval_subparsers.add_parser(
        "contradict",
        help="Score the contradiction detector: conflict-detection precision/recall/F1.",
    )
    contradict_eval_parser.add_argument(
        "--labels",
        type=Path,
        default=_CONTRADICT_LABELS,
        help="Contradiction cases (default: labels/contradict_seed.jsonl).",
    )
    ingest_parser = subparsers.add_parser(
        "ingest",
        help="Ingest a source folder into a bundle behind the plan->approve->commit gate.",
    )
    ingest_parser.add_argument(
        "source",
        type=Path,
        help="Source folder (Markdown) to ingest.",
    )
    ingest_parser.add_argument(
        "--bundle",
        type=Path,
        default=_DEFAULT_BUNDLE,
        help="Target OKF bundle directory (default: bundles/northwind).",
    )
    ingest_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and print the plan without writing or committing.",
    )
    ingest_parser.add_argument(
        "--yes",
        action="store_true",
        help="Approve the plan non-interactively (explicit human approval).",
    )
    ingest_parser.add_argument(
        "--authority",
        type=int,
        default=0,
        help="Source authority rank for contradiction resolution (default: 0).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI. With no subcommand, print help and exit cleanly."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "validate":
        return _run_validate(args.bundle)
    if args.command == "bench":
        if getattr(args, "bench_command", None) == "acceptance":
            return _run_bench_acceptance(args.bundle, args.report)
        if getattr(args, "bench_command", None) == "corpus":
            return _run_bench_corpus(args.out)
        if getattr(args, "bench_command", None) == "realworld":
            return _run_bench_realworld(args)
        return _run_bench(args.bundle, args.report)
    if args.command == "eval":
        return _run_eval(args)
    if args.command == "ingest":
        return _run_ingest(args)
    if args.command == "calibrate":
        return _run_calibrate(args)
    parser.print_help()
    return 0


def _run_ingest(args: argparse.Namespace) -> int:
    """Run ``kosha ingest``: build the plan, route it, and commit on approval."""
    if not args.source.is_dir():
        print(f"kosha: not a source directory: {args.source}", file=sys.stderr)
        return 2
    if not args.bundle.is_dir():
        print(f"kosha: not a bundle directory: {args.bundle}", file=sys.stderr)
        return 2
    reader = input if sys.stdin.isatty() and not args.yes else None
    result = ingest(
        args.source,
        args.bundle,
        asof=datetime.now(UTC),
        source_authority=args.authority,
        dry_run=args.dry_run,
        assume_yes=args.yes,
        reader=reader,
    )
    print(render_plan(result.plan))
    print()
    print(render_routing(result.routing))
    if args.dry_run:
        print("\ndry run: no changes written.")
        return 0
    if result.committed and result.commit_sha is not None:
        print(
            f"\ncommitted {result.commit_sha[:8]} on {result.branch} "
            f"(backup {result.backup_tag})."
        )
    else:
        print("\nnot approved: nothing committed.")
    return 0


def _run_validate(bundle: Path) -> int:
    """Validate ``bundle`` and return a process exit code (0 = conformant)."""
    if not bundle.is_dir():
        print(f"kosha: not a bundle directory: {bundle}", file=sys.stderr)
        return 2
    report = validate_bundle(bundle)
    for finding in report.findings:
        print(f"{finding.severity.value}: {finding.path}: [{finding.rule.value}] {finding.message}")
    errors = len(report.errors)
    warnings = len(report.warnings)
    if errors:
        print(f"FAIL: {bundle} is not OKF-conformant ({errors} error(s), {warnings} warning(s))")
        return 1
    print(f"OK: {bundle} is OKF-conformant ({warnings} warning(s))")
    return 0

def _run_bench_corpus(out_dir: Path) -> int:
    """Regenerate the external stdlib benchmark corpus into ``out_dir``."""
    stats = build_corpus(out_dir)
    print(
        f"Wrote {stats.concept_count} concepts across {stats.module_count} modules "
        f"to {out_dir}"
    )
    return 0


def _run_bench_realworld(args: argparse.Namespace) -> int:
    """Run the M13 real-model benchmark; exit 0 on GO, 1 on NO-GO."""
    if getattr(args, "gate2", False):
        return _run_bench_gate2(args)
    if not args.corpus.is_dir():
        print(f"kosha: not a bundle directory: {args.corpus}", file=sys.stderr)
        return 2
    config = RealworldConfig(
        corpus=args.corpus,
        queries=args.queries,
        maintenance=args.maintenance,
        guidance=args.guidance,
        ingests=args.ingests,
        drift_seed_concepts=args.seed_concepts,
        max_queries=args.max_queries,
    )

    def _progress(message: str) -> None:
        print(f"[realworld] {message}", file=sys.stderr, flush=True)

    embedding_provider = resolve_embedding_provider()
    mismatch = default_threshold_mismatch(embedding_provider, DEFAULT_THRESHOLDS)
    if mismatch is not None:
        print(f"kosha: warning: {mismatch}", file=sys.stderr)
    report = run_realworld(
        config,
        embedding_provider,
        resolve_generation_provider(),
        progress=_progress,
    )
    print(
        f"Real-model benchmark over {args.corpus} ({report.concept_count} concepts, "
        f"embed={report.embedding_provider}, gen={report.generation_provider})"
    )
    print(
        f"Maintenance accuracy: loop {report.maintenance_by_name('kosha_loop').accuracy:.2f} "
        f"vs prompt-only {report.maintenance_by_name('prompt_only').accuracy:.2f} "
        f"(delta {report.maintenance_delta:+.2f})"
    )
    print(
        f"Contradiction safety: loop {report.safety_by_name('kosha_loop').safety_rate:.2f} "
        f"vs prompt-only {report.safety_by_name('prompt_only').safety_rate:.2f} "
        f"(delta {report.safety_delta:+.2f}, the reframed Gate-0 moat)"
    )
    print(f"Gate 0 verdict: {report.verdict}")
    if args.report is not None:
        args.report.write_text(render_realworld_report(report), encoding="utf-8")
        print(f"Wrote report to {args.report}")
    return 0 if report.verdict == "GO" else 1


def _run_bench_gate2(args: argparse.Namespace) -> int:
    """Run the pre-registered Gate-0 v2 re-test across the provider matrix.

    Exit 0 on GO (M14+ authorized), 1 on NO-GO (ship-as-skill stands).
    """
    if not args.corpus.is_dir():
        print(f"kosha: not a bundle directory: {args.corpus}", file=sys.stderr)
        return 2
    config = RealworldConfig(
        corpus=args.corpus,
        queries=args.queries,
        maintenance=args.maintenance,
        guidance=args.guidance,
        contradictions=args.contradictions,
    )

    def _progress(message: str) -> None:
        print(f"[gate2] {message}", file=sys.stderr, flush=True)

    criterion = Gate2Criterion.preregistered()
    matrix = resolve_provider_matrix()
    cases = load_contradictions(config.contradictions)
    measure = build_gate2_measure(config)
    _progress("verifying auditability guarantee + provenance replay")
    with tempfile.TemporaryDirectory() as scratch:
        auditability = run_auditability(cases, work_dir=Path(scratch))
    report = run_gate2(
        matrix,
        measure,
        criterion=criterion,
        runs=args.runs,
        audit_verified=auditability.verified,
        progress=_progress,
    )
    concept_count = len(load_bundle(config.corpus).concepts)
    print("Pre-registered Gate-0 v2 criterion:")
    print(criterion.describe())
    print(
        f"Matrix: {len(report.embeddings)} embeddings x {len(report.generations)} "
        f"generation models, {report.runs} runs/cell, "
        f"{len(cases)} held-out contradictions/cell."
    )
    for cell in report.cells:
        for axis in cell.axes:
            print(
                f"  {cell.embedding_label} x {cell.generation_label} | {axis.axis}: "
                f"loop {axis.loop.median:.2f} [{axis.loop.lo:.2f}, {axis.loop.hi:.2f}] vs "
                f"prompt {axis.prompt.median:.2f} [{axis.prompt.lo:.2f}, {axis.prompt.hi:.2f}] "
                f"(Δ {axis.median_delta:+.2f}, cleared={axis.cleared(criterion.quality_margin)})"
            )
    print(
        f"Auditability: guarantee verified={auditability.guarantee_verified}, "
        f"provenance replayable={auditability.provenance_replayable}"
    )
    print(f"Gate-0 v2 verdict: {report.verdict}")
    print(f"M14+ authorized: {report.authorizes_m14}")
    if report.carrying_axis is not None:
        print(f"Carrying axis: {report.carrying_axis}")
    if args.report is not None:
        args.report.write_text(
            render_gate2_report(
                report, auditability, corpus_path=str(config.corpus), concept_count=concept_count
            ),
            encoding="utf-8",
        )
        print(f"Wrote report to {args.report}")
    return 0 if report.verdict == "GO" else 1


def _run_calibrate(args: argparse.Namespace) -> int:
    """Fit the dedup thresholds to the configured embedding on the seed labels."""
    if not args.labels.is_file():
        print(f"kosha: not a labels file: {args.labels}", file=sys.stderr)
        return 2
    pairs = load_dedup_pairs(args.labels)
    calibration = calibrate_thresholds(
        pairs, resolve_embedding_provider(), margin=args.margin
    )
    print(render_calibration(calibration))
    return 0


def _run_bench(bundle_path: Path, report_path: Path | None) -> int:
    """Run the benchmark + dedup gate on ``bundle_path``; optionally write a report."""
    if not bundle_path.is_dir():
        print(f"kosha: not a bundle directory: {bundle_path}", file=sys.stderr)
        return 2
    bundle = load_bundle(bundle_path)
    embedding_provider = resolve_embedding_provider()
    report = run_benchmark(bundle, embedding_provider, resolve_generation_provider())
    dedup = evaluate_threshold_only(load_dedup_pairs(_DEDUP_LABELS), embedding_provider)
    granularity = evaluate_granularity(load_granularity_labels(_GRANULARITY_LABELS))
    kill_signals = evaluate_kill_signals(report, dedup)
    verdict = go_no_go(kill_signals)
    print(
        f"Benchmark over {bundle_path} "
        f"({report.query_count} queries, embed={report.embedding_provider}, "
        f"gen={report.generation_provider})"
    )
    print(render_table(report))
    for signal in kill_signals:
        print(f"{signal.id}: {signal.verdict}")
    print(f"Premise verdict: {verdict}")
    if report_path is not None:
        document = render_premise_report(
            bundle_path=str(bundle_path),
            concept_count=len(bundle.concepts),
            max_depth=_max_depth(bundle.concepts),
            report=report,
            dedup=dedup,
            granularity=granularity,
            kill_signals=kill_signals,
        )
        report_path.write_text(document, encoding="utf-8")
        print(f"Wrote report to {report_path}")
    return 0


def _run_bench_acceptance(bundle_path: Path, report_path: Path | None) -> int:
    """Gate the MVP success criteria; exit 0 iff every criterion passes."""
    if not bundle_path.is_dir():
        print(f"kosha: not a bundle directory: {bundle_path}", file=sys.stderr)
        return 2
    bundle = load_bundle(bundle_path)
    report = run_acceptance(
        bundle,
        resolve_embedding_provider(),
        resolve_generation_provider(),
        bundle_path=str(bundle_path),
    )
    print(
        f"MVP acceptance over {bundle_path} "
        f"({report.concept_count} concepts, embed={report.embedding_provider}, "
        f"gen={report.generation_provider})"
    )
    for criterion in report.criteria:
        status = "PASS" if criterion.passed else "FAIL"
        print(f"{criterion.id}: {status} — {criterion.name}")
    verdict = "PASS" if report.passed else "FAIL"
    print(f"MVP success contract: {verdict}")
    if report_path is not None:
        report_path.write_text(render_acceptance_report(report), encoding="utf-8")
        print(f"Wrote report to {report_path}")
    return 0 if report.passed else 1


def _run_eval(args: argparse.Namespace) -> int:
    """Dispatch ``kosha eval <suite>``."""
    if args.eval_command == "extract":
        return _run_eval_extract(args.labels)
    if args.eval_command == "dedup":
        return _run_eval_dedup(args.labels, args.bundle)
    if args.eval_command == "merge":
        return _run_eval_merge(args.labels)
    if args.eval_command == "relate":
        return _run_eval_relate(args.labels)
    if args.eval_command == "contradict":
        return _run_eval_contradict(args.labels)
    print("kosha: usage: kosha eval {extract,dedup,merge,relate,contradict} [...]", file=sys.stderr)
    return 2


def _run_eval_extract(labels_path: Path) -> int:
    """Score the concept extractor against the seed granularity labels."""
    if not labels_path.is_file():
        print(f"kosha: labels file not found: {labels_path}", file=sys.stderr)
        return 2
    provider = resolve_generation_provider()
    report = evaluate_extractor(load_granularity_labels(labels_path), provider)
    print(
        f"Extractor eval over {labels_path} "
        f"({report.label_count} labels, gen={provider.name})"
    )
    print(f"boundary accuracy: {report.score:.3f} ({report.correct}/{report.label_count})")
    return 0


def _run_eval_dedup(labels_path: Path, bundle_path: Path) -> int:
    """Score the dedup resolver: pair precision/recall + repeated-ingest duplicate rate."""
    if not labels_path.is_file():
        print(f"kosha: labels file not found: {labels_path}", file=sys.stderr)
        return 2
    if not bundle_path.is_dir():
        print(f"kosha: not a bundle directory: {bundle_path}", file=sys.stderr)
        return 2
    embedding_provider = resolve_embedding_provider()
    adjudicator = LexicalAdjudicator()
    report = evaluate_dedup(
        load_dedup_pairs(labels_path), embedding_provider, adjudicator=adjudicator
    )
    duplicates = evaluate_duplicate_rate(
        load_bundle(bundle_path), embedding_provider, adjudicator=adjudicator
    )
    print(
        f"Dedup eval over {labels_path} "
        f"({report.pair_count} pairs, embed={embedding_provider.name}, adj={adjudicator.name})"
    )
    print(
        f"precision: {report.precision:.3f}  recall: {report.recall:.3f}  "
        f"accuracy: {report.accuracy:.3f}"
    )
    print(
        f"duplicate-rate: {duplicates.duplicate_rate:.3f} "
        f"({duplicates.created} created / {duplicates.concept_count} concepts on repeated ingest)"
    )
    return 0


def _run_eval_merge(labels_path: Path) -> int:
    """Score the merge surface's claim-targeting accuracy against seed cases."""
    if not labels_path.is_file():
        print(f"kosha: labels file not found: {labels_path}", file=sys.stderr)
        return 2
    targeter = LexicalClaimTargeter()
    report = evaluate_merge(load_merge_cases(labels_path), targeter)
    print(f"Merge eval over {labels_path} ({report.case_count} cases, targeter={targeter.name})")
    print(f"targeting accuracy: {report.score:.3f} ({report.correct}/{report.case_count})")
    return 0


def _run_eval_relate(labels_path: Path) -> int:
    """Score the cross-linker relate surface: link-discovery precision/recall/F1."""
    if not labels_path.is_file():
        print(f"kosha: labels file not found: {labels_path}", file=sys.stderr)
        return 2
    relator = LexicalRelator()
    report = evaluate_relate(load_relate_cases(labels_path), relator)
    print(f"Relate eval over {labels_path} ({report.case_count} cases, relator={relator.name})")
    print(
        f"precision: {report.precision:.3f}  recall: {report.recall:.3f}  f1: {report.f1:.3f} "
        f"({report.true_positives}/{report.gold_total} gold edges)"
    )
    return 0


def _run_eval_contradict(labels_path: Path) -> int:
    """Score the contradiction detector: conflict-detection precision/recall/F1."""
    if not labels_path.is_file():
        print(f"kosha: labels file not found: {labels_path}", file=sys.stderr)
        return 2
    judge = LexicalContradictionJudge()
    report = evaluate_contradict(load_contradict_cases(labels_path), judge)
    print(f"Contradict eval over {labels_path} ({report.case_count} cases, judge={judge.name})")
    print(
        f"precision: {report.precision:.3f}  recall: {report.recall:.3f}  "
        f"f1: {report.f1:.3f}  accuracy: {report.accuracy:.3f}"
    )
    return 0


def _max_depth(concept_ids: Iterable[str]) -> int:
    """Return the deepest concept path depth (segments) in the bundle."""
    return max((cid.count("/") + 1 for cid in concept_ids), default=0)


if __name__ == "__main__":
    raise SystemExit(main())
