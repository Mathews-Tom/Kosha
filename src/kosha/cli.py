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
from kosha.okf import load_bundle
from kosha.providers import resolve_embedding_provider, resolve_generation_provider
from kosha.validate import validate_bundle

# Default golden corpus the benchmark runs against, and the seed label files.
_DEFAULT_BUNDLE = Path("bundles/northwind")
_DEDUP_LABELS = Path("labels/dedup_seed.jsonl")
_GRANULARITY_LABELS = Path("labels/granularity_seed.jsonl")


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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI. With no subcommand, print help and exit cleanly."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "validate":
        return _run_validate(args.bundle)
    if args.command == "bench":
        return _run_bench(args.bundle, args.report)
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


def _max_depth(concept_ids: Iterable[str]) -> int:
    """Return the deepest concept path depth (segments) in the bundle."""
    return max((cid.count("/") + 1 for cid in concept_ids), default=0)


if __name__ == "__main__":
    raise SystemExit(main())
