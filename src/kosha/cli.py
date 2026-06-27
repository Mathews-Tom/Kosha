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
from collections.abc import Sequence
from pathlib import Path

from kosha import __version__
from kosha.bench import render_table, run_benchmark
from kosha.okf import load_bundle
from kosha.providers import resolve_embedding_provider, resolve_generation_provider
from kosha.validate import validate_bundle

# Default golden corpus the benchmark runs against.
_DEFAULT_BUNDLE = Path("bundles/northwind")


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
    """Run the benchmark on ``bundle_path``; optionally write a report."""
    if not bundle_path.is_dir():
        print(f"kosha: not a bundle directory: {bundle_path}", file=sys.stderr)
        return 2
    bundle = load_bundle(bundle_path)
    report = run_benchmark(
        bundle,
        resolve_embedding_provider(),
        resolve_generation_provider(),
    )
    table = render_table(report)
    print(
        f"Benchmark over {bundle_path} "
        f"({report.query_count} queries, embed={report.embedding_provider}, "
        f"gen={report.generation_provider})"
    )
    print(table)
    if report_path is not None:
        document = _render_document(bundle_path, table)
        report_path.write_text(document, encoding="utf-8")
        print(f"Wrote report to {report_path}")
    return 0


def _render_document(bundle_path: Path, table: str) -> str:
    """Render a minimal benchmark report document (table only)."""
    return (
        "# Kosha Premise Benchmark\n\n"
        f"Corpus: `{bundle_path}`\n\n"
        "## Strategy comparison\n\n"
        f"{table}\n"
    )


if __name__ == "__main__":
    raise SystemExit(main())
