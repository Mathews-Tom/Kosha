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
from collections.abc import Iterable, Sequence
from pathlib import Path

from kosha import __version__
from kosha.bench import (
    evaluate_granularity,
    evaluate_kill_signals,
    evaluate_threshold_only,
    go_no_go,
    load_dedup_pairs,
    load_granularity_labels,
    render_premise_report,
    render_table,
    run_benchmark,
)
from kosha.dedup import LexicalAdjudicator
from kosha.eval import (
    evaluate_dedup,
    evaluate_duplicate_rate,
    evaluate_extractor,
    evaluate_merge,
    load_merge_cases,
)
from kosha.merge import LexicalClaimTargeter
from kosha.okf import load_bundle
from kosha.providers import resolve_embedding_provider, resolve_generation_provider
from kosha.validate import validate_bundle

# Default golden corpus the benchmark runs against, and the seed label files.
_DEFAULT_BUNDLE = Path("bundles/northwind")
_DEDUP_LABELS = Path("labels/dedup_seed.jsonl")
_GRANULARITY_LABELS = Path("labels/granularity_seed.jsonl")
_MERGE_LABELS = Path("labels/merge_seed.jsonl")


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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI. With no subcommand, print help and exit cleanly."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "validate":
        return _run_validate(args.bundle)
    if args.command == "bench":
        return _run_bench(args.bundle, args.report)
    if args.command == "eval":
        return _run_eval(args)
    parser.print_help()
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


def _run_eval(args: argparse.Namespace) -> int:
    """Dispatch ``kosha eval <suite>``."""
    if args.eval_command == "extract":
        return _run_eval_extract(args.labels)
    if args.eval_command == "dedup":
        return _run_eval_dedup(args.labels, args.bundle)
    if args.eval_command == "merge":
        return _run_eval_merge(args.labels)
    print("kosha: usage: kosha eval {extract,dedup,merge} [...]", file=sys.stderr)
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


def _max_depth(concept_ids: Iterable[str]) -> int:
    """Return the deepest concept path depth (segments) in the bundle."""
    return max((cid.count("/") + 1 for cid in concept_ids), default=0)


if __name__ == "__main__":
    raise SystemExit(main())
