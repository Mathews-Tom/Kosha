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
import json
import os
import sys
import time
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from kosha import __version__, cli_json
from kosha.approve import (
    PlanRouting,
    Reader,
    ReviewQueue,
    normalize_reviewer,
    render_plan,
    render_routing,
    request_item_decisions,
)
from kosha.audit import build_report, require_export_access, to_json, to_markdown
from kosha.bench import (
    assert_seed_labels_path,
    calibrate_adjudicator_threshold,
    calibrate_relator_threshold,
    calibrate_targeter_threshold,
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
    render_single_threshold_calibration,
    render_table,
    run_benchmark,
)
from kosha.bench.acceptance import render_acceptance_report, run_acceptance
from kosha.bench.corpus import CORPUS_NAME, build_corpus
from kosha.bench.realworld import (
    RealworldConfig,
    local_provider_gate_warning,
    render_realworld_report,
    run_realworld,
)
from kosha.contradiction import LexicalContradictionJudge
from kosha.dedup import DEFAULT_THRESHOLDS, LexicalAdjudicator
from kosha.eval import (
    evaluate_contradict,
    evaluate_contradict_by_regime,
    evaluate_dedup,
    evaluate_duplicate_rate,
    evaluate_extractor,
    evaluate_merge,
    evaluate_relate,
    load_contradict_cases,
    load_merge_cases,
    load_relate_cases,
)
from kosha.evidence import EvidenceCorruptionError, EvidenceStore
from kosha.evidence.model import SourceRun
from kosha.evidence.paths import evidence_root
from kosha.evidence.replay import ReplayError, render_replay_text, replay_run
from kosha.evidence.verify import render_verification_text, verify_evidence
from kosha.git_store import GitStore
from kosha.ingest.url import UrlIngestError
from kosha.ingest.watch import ScheduledIngest, SourcePolicy
from kosha.link import LexicalRelator
from kosha.mcp.service import AccessDeniedError, resolve_bundle_access, resolve_clearance
from kosha.merge import LexicalClaimTargeter
from kosha.okf import load_bundle
from kosha.pipeline import IngestResult, commit_reviewed_plan, ingest
from kosha.plan import build_plan
from kosha.providers import resolve_embedding_provider, resolve_generation_provider
from kosha.providers.diagnostics import diagnose_embedding_provider, diagnose_generation_provider
from kosha.recovery import (
    RecoveryError,
    append_audit_log,
    apply_reindex,
    apply_restore,
    describe_reindex,
    describe_restore,
    list_backups,
)
from kosha.release import ReleaseError, create_release
from kosha.server import make_http_server
from kosha.server.registry import build_bundles_dir_registry, build_single_bundle_registry
from kosha.sync import render_sync_check_text, run_sync_check, sync_check_json
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
        description="Auditable OKF governance toolkit.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command")
    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Diagnostic tools.",
    )
    doctor_subparsers = doctor_parser.add_subparsers(dest="doctor_command", required=True)
    doctor_subparsers.add_parser(
        "providers",
        help="Diagnose configured AI providers.",
    )
    validate_parser = subparsers.add_parser(
        "validate",
        help="Check an OKF bundle for v0.1 conformance.",
    )
    validate_parser.add_argument(
        "bundle",
        type=Path,
        help="Path to the OKF bundle directory.",
    )
    validate_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the result as structured JSON instead of text.",
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
    bench_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the result as structured JSON instead of text.",
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
    acceptance_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the result as structured JSON instead of text.",
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
        "--fidelity-targeter",
        choices=("lexical", "generation"),
        default="lexical",
        help="Claim targeter used by the fidelity probe (default: lexical).",
    )
    realworld_parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Write the acceptance report to this path.",
    )
    realworld_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the result as structured JSON instead of text.",
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
    calibrate_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the result as structured JSON instead of text.",
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
    extract_eval_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the result as structured JSON instead of text.",
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
    dedup_eval_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the result as structured JSON instead of text.",
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
    merge_eval_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the result as structured JSON instead of text.",
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
    relate_eval_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the result as structured JSON instead of text.",
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
    contradict_eval_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the result as structured JSON instead of text.",
    )
    ingest_parser = subparsers.add_parser(
        "ingest",
        help="Ingest a source folder into a bundle behind the plan->approve->commit gate.",
    )
    ingest_parser.add_argument(
        "source",
        type=str,
        help="Source folder (Markdown), or HTTP(S) URL when --watch is set.",
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
    approval_group = ingest_parser.add_mutually_exclusive_group()
    approval_group.add_argument(
        "--yes",
        action="store_true",
        help="Approve the whole plan non-interactively (explicit human approval).",
    )
    approval_group.add_argument(
        "--review",
        action="store_true",
        help=(
            "Approve or reject each plan item individually instead of one "
            "blanket yes/no; an escalated conflict must be acknowledged before "
            "any change commits."
        ),
    )
    ingest_parser.add_argument(
        "--authority",
        type=int,
        default=0,
        help="Source authority rank for contradiction resolution (default: 0).",
    )
    ingest_parser.add_argument(
        "--reviewer",
        type=str,
        default=None,
        help=(
            "Approving reviewer's identity (e.g. 'Jane Doe <jane@example.com>'), "
            "recorded as a Reviewed-by trailer on the commit."
        ),
    )
    ingest_parser.add_argument(
        "--watch",
        action="store_true",
        help="Run guarded scheduled re-ingest instead of a single immediate ingest.",
    )
    ingest_parser.add_argument(
        "--interval-seconds",
        type=float,
        default=60.0,
        help="Watch interval in seconds when --watch is set (default: 60).",
    )
    ingest_parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Number of scheduled runs before exiting; 0 means run until interrupted.",
    )
    ingest_parser.add_argument(
        "--url-max-bytes",
        type=int,
        default=10 * 1024 * 1024,
        help="Maximum bytes accepted from each scheduled URL source.",
    )
    ingest_parser.add_argument(
        "--allowed-host",
        action="append",
        default=[],
        help="Allowed scheduled URL hostname; may be repeated.",
    )
    ingest_parser.add_argument(
        "--review-queue",
        type=Path,
        default=None,
        help="Append BLOCK-lane items to this shared review queue JSON file.",
    )
    ingest_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the result as structured JSON instead of text.",
    )
    serve_parser = subparsers.add_parser(
        "serve",
        help="Serve traversal-only bundle access over a local HTTP/SSE boundary.",
    )
    source_group = serve_parser.add_mutually_exclusive_group()
    source_group.add_argument(
        "--bundle",
        type=Path,
        default=_DEFAULT_BUNDLE,
        help="Single OKF bundle directory to serve (default: bundles/northwind).",
    )
    source_group.add_argument(
        "--bundles-dir",
        type=Path,
        default=None,
        help="Directory whose direct children are served as bundle ids.",
    )
    serve_parser.add_argument(
        "--bundle-id",
        type=str,
        default="default",
        help="Client-facing id for --bundle mode (default: default).",
    )
    serve_parser.add_argument(
        "--bundle-access",
        action="append",
        default=[],
        help=(
            "Access label. In --bundle mode pass LABEL or bundle_id=LABEL; "
            "in --bundles-dir mode pass bundle_id=LABEL. May be repeated."
        ),
    )
    serve_parser.add_argument(
        "--allow-open-bundles",
        action="store_true",
        help="Permit bundles without an access label in --bundles-dir mode.",
    )
    serve_parser.add_argument(
        "--clearance",
        action="append",
        default=[],
        help="Caller clearance label; may be repeated. Also reads KOSHA_CLEARANCE.",
    )
    serve_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host interface to bind (default: 127.0.0.1).",
    )
    serve_parser.add_argument(
        "--allow-non-loopback",
        action="store_true",
        help="Allow binding the served boundary to a non-loopback host.",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="TCP port to bind (default: 8765).",
    )
    serve_parser.add_argument(
        "--once",
        action="store_true",
        help="Build the server and exit without serving; intended for smoke tests.",
    )
    queue_parser = subparsers.add_parser(
        "review-queue",
        help="Inspect or record decisions in a shared BLOCK-lane review queue.",
    )
    queue_subparsers = queue_parser.add_subparsers(dest="queue_command")
    queue_list_parser = queue_subparsers.add_parser(
        "list",
        help="List queued BLOCK-lane review items.",
    )
    queue_list_parser.add_argument("queue", type=Path, help="Review queue JSON file.")
    queue_decide_parser = queue_subparsers.add_parser(
        "decide",
        help="Append a reviewer decision to a queued item.",
    )
    queue_decide_parser.add_argument("queue", type=Path, help="Review queue JSON file.")
    queue_decide_parser.add_argument("item_id", type=str, help="Queued item id.")
    queue_decide_parser.add_argument(
        "decision",
        choices=("approve", "reject"),
        help="Decision to append to the item's audit history.",
    )
    queue_decide_parser.add_argument(
        "--reviewer",
        required=True,
        help="Reviewer identity to record with the decision.",
    )
    export_parser = subparsers.add_parser(
        "export",
        help="Export compliance-grade audit evidence for a bundle's git history.",
    )
    export_parser.add_argument(
        "bundle",
        type=Path,
        help="Path to the OKF bundle directory (a Git repository).",
    )
    export_parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="Export format (default: json).",
    )
    export_parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write the export to this path instead of stdout.",
    )
    export_parser.add_argument(
        "--ref",
        type=str,
        default="HEAD",
        help="Git ref to walk for ingest history (default: HEAD).",
    )
    export_parser.add_argument(
        "--include-source-text",
        action="store_true",
        help=(
            "Include each changed file's committed content. Default: metadata "
            "only, since source body text may be sensitive."
        ),
    )
    evidence_parser = subparsers.add_parser(
        "evidence",
        help="Verify, inspect, and replay stored evidence for a bundle.",
    )
    evidence_subparsers = evidence_parser.add_subparsers(dest="evidence_command")
    evidence_verify_parser = evidence_subparsers.add_parser(
        "verify",
        help="Verify every stored evidence manifest, object, and commit trailer.",
    )
    evidence_verify_parser.add_argument(
        "bundle",
        type=Path,
        help="Path to the OKF bundle directory (a Git repository).",
    )
    evidence_verify_parser.add_argument(
        "--ref",
        type=str,
        default="HEAD",
        help="Git ref to walk for ingest commit trailers (default: HEAD).",
    )
    evidence_verify_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the result as structured JSON instead of text.",
    )
    evidence_show_parser = evidence_subparsers.add_parser(
        "show",
        help="Show one stored source-run's metadata (--content also prints its evidence text).",
    )
    evidence_show_parser.add_argument(
        "bundle",
        type=Path,
        help="Path to the OKF bundle directory (a Git repository).",
    )
    evidence_show_parser.add_argument(
        "run_id",
        type=str,
        help="Source-run id (see 'kosha evidence verify' or a commit's Source-Run trailer).",
    )
    evidence_show_parser.add_argument(
        "--content",
        action="store_true",
        help=(
            "Also print each evidence document's exact normalized text. "
            "Default: metadata only, since source body text may be sensitive."
        ),
    )
    evidence_show_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the result as structured JSON instead of text.",
    )
    evidence_replay_parser = evidence_subparsers.add_parser(
        "replay",
        help="Replay a stored source run through the current pipeline as a zero-network dry run.",
    )
    evidence_replay_parser.add_argument(
        "bundle",
        type=Path,
        help="Path to the OKF bundle directory (a Git repository).",
    )
    evidence_replay_parser.add_argument(
        "run_id",
        type=str,
        help="Source-run id to replay.",
    )
    evidence_replay_parser.add_argument(
        "--ref",
        type=str,
        default="HEAD",
        help="Git ref to look up the run's original commit on, for a path diff (default: HEAD).",
    )
    evidence_replay_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the result as structured JSON instead of text.",
    )
    recover_parser = subparsers.add_parser(
        "recover",
        help="Backup-tag-based recovery: list backups, restore, or reindex.",
    )
    recover_subparsers = recover_parser.add_subparsers(dest="recover_command")
    backups_parser = recover_subparsers.add_parser(
        "backups",
        help="List available backup tags.",
    )
    backups_parser.add_argument(
        "bundle",
        type=Path,
        help="Path to the OKF bundle directory (a Git repository).",
    )
    backups_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the result as structured JSON instead of text.",
    )
    restore_parser = recover_subparsers.add_parser(
        "restore",
        help="Restore a bundle to a backup tag's recorded state.",
    )
    restore_parser.add_argument(
        "bundle",
        type=Path,
        help="Path to the OKF bundle directory (a Git repository).",
    )
    restore_parser.add_argument(
        "--tag",
        type=str,
        required=True,
        help="Backup tag to restore to (see 'kosha recover backups'), e.g. backup/2026-07-01.",
    )
    restore_parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually perform the restore. Default is dry-run: show the plan only.",
    )
    restore_parser.add_argument(
        "--branch",
        type=str,
        default=None,
        help="Branch to commit the restore on (default: recovery/restore-<tag>-<timestamp>).",
    )
    restore_parser.add_argument(
        "--audit-log",
        type=Path,
        default=None,
        help="Append the audit record to this JSONL file.",
    )
    restore_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the result as structured JSON instead of text.",
    )
    reindex_parser = recover_subparsers.add_parser(
        "reindex",
        help="Regenerate index.md files that drifted from the bundle's concepts.",
    )
    reindex_parser.add_argument(
        "bundle",
        type=Path,
        help="Path to the OKF bundle directory (a Git repository).",
    )
    reindex_parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually write and commit the reindex. Default is dry-run: show the plan only.",
    )
    reindex_parser.add_argument(
        "--branch",
        type=str,
        default=None,
        help="Branch to commit the reindex on (default: recovery/reindex-<timestamp>).",
    )
    reindex_parser.add_argument(
        "--audit-log",
        type=Path,
        default=None,
        help="Append the audit record to this JSONL file.",
    )
    reindex_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the result as structured JSON instead of text.",
    )
    sync_parser = subparsers.add_parser(
        "sync",
        help="Check generated public surfaces against deterministic sources.",
    )
    sync_subparsers = sync_parser.add_subparsers(dest="sync_command")
    sync_check_parser = sync_subparsers.add_parser(
        "check",
        help="Report generated public-surface drift without writing files.",
    )
    sync_check_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the result as structured JSON instead of text.",
    )
    sync_subparsers.add_parser(
        "docs",
        help="Write deterministic public-surface docs sections.",
    )
    sync_subparsers.add_parser(
        "status",
        help="Write benchmark and status surfaces.",
    )
    agent_fragment_parser = sync_subparsers.add_parser(
        "agent-fragment",
        help="Install or update the Kosha traversal fragment in an agent instruction file.",
    )
    agent_fragment_parser.add_argument(
        "--target",
        type=Path,
        required=True,
        help="Path to the instruction file (e.g. AGENTS.md, CLAUDE.md).",
    )
    agent_fragment_parser.add_argument(
        "--bundle",
        type=Path,
        required=True,
        help="Path to the OKF bundle.",
    )
    agent_fragment_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the result as structured JSON instead of text.",
    )
    release_parser = subparsers.add_parser(
        "release",
        help="Tag a validated bundle as an immutable, reproducible release.",
    )
    release_parser.add_argument(
        "bundle",
        type=Path,
        help="Path to the OKF bundle directory (a Git repository).",
    )
    release_parser.add_argument(
        "--tag",
        type=str,
        required=True,
        help="Release version, e.g. v1 (tagged as release/v1).",
    )
    release_parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Export a content-addressed archive (.zip or .tar) to this path.",
    )
    release_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the result as structured JSON instead of text.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI. With no subcommand, print help and exit cleanly."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "validate":
        return _run_validate(args.bundle, args.json)
    elif args.command == "doctor" and getattr(args, "doctor_command", None) == "providers":
        return _run_doctor_providers(args)
    if args.command == "bench":
        if getattr(args, "bench_command", None) == "acceptance":
            return _run_bench_acceptance(args.bundle, args.report, args.json)
        if getattr(args, "bench_command", None) == "corpus":
            return _run_bench_corpus(args.out)
        if getattr(args, "bench_command", None) == "realworld":
            return _run_bench_realworld(args)
        return _run_bench(args.bundle, args.report, args.json)
    if args.command == "eval":
        return _run_eval(args)
    if args.command == "ingest":
        return _run_ingest(args)
    if args.command == "serve":
        return _run_serve(args)
    if args.command == "review-queue":
        return _run_review_queue(args)
    if args.command == "export":
        return _run_export(args)
    if args.command == "evidence":
        return _run_evidence(args)
    if args.command == "calibrate":
        return _run_calibrate(args)
    if args.command == "sync":
        return _run_sync(args)
    if args.command == "recover":
        return _run_recover(args)
    if args.command == "release":
        return _run_release(args)
    parser.print_help()
    return 0


def _run_sync(args: argparse.Namespace) -> int:
    """Run ``kosha sync`` subcommands."""
    if args.sync_command == "agent-fragment":
        return _run_sync_agent_fragment(args)
    if args.sync_command not in ("check", "docs", "status"):
        print(
            "kosha: sync requires a subcommand: check, docs, status, agent-fragment",
            file=sys.stderr,
        )
        return 2

    repo_root = Path.cwd()
    if args.sync_command == "check":
        report = run_sync_check(repo_root)
        if args.json:
            print(cli_json.dumps(sync_check_json(report)))
        else:
            print(render_sync_check_text(report))
        return 0 if report.ok else 1
        
    # Writers: docs, status
    from kosha.sync.decision import current_git_head, decide_sync
    from kosha.sync.snapshot import content_snapshot
    from kosha.sync.state import (
        SyncState,
        load_sync_state,
        save_sync_state,
        sync_state_path,
    )
    
    state_path = sync_state_path(repo_root)
    state = load_sync_state(state_path) if state_path.is_file() else None
    
    snap = content_snapshot(repo_root)
    
    if state and state.command == args.sync_command:
        decision = decide_sync(
            repo_root,
            recorded_git_head=state.git_head,
            recorded_updated_at=state.updated_at,
            recorded_content_snapshot=state.content_snapshot,
            current_content_snapshot=snap,
            source_paths=["src/kosha", "tests"],
        )
        if decision.noop:
            print(f"Kosha sync {args.sync_command}: no changes required ({decision.reason}).")
            return 0
            
    # Do writes based on command
    if args.sync_command == "docs":
        from kosha.sync.cli_reference import write_cli_reference, write_readme_cli_overview
        from kosha.sync.traversal import write_fallback_artifacts, write_mcp_integration_doc
        
        write_cli_reference(repo_root)
        write_readme_cli_overview(repo_root)
        write_mcp_integration_doc(repo_root)
        write_fallback_artifacts(repo_root)
        
    elif args.sync_command == "status":
        from kosha.sync.status_surfaces import write_gate0_status, write_readme_acceptance_table
        write_readme_acceptance_table(repo_root)
        write_gate0_status(repo_root)
        
    # Re-snapshot to record the new hash
    new_snap = content_snapshot(repo_root)
    if not state or new_snap.sha256 != state.content_snapshot or state.command != args.sync_command:
        head = current_git_head(repo_root)
        
        from datetime import UTC, datetime

        from kosha import __version__
        
        new_state = SyncState(
            updated_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            command=args.sync_command,
            git_head=head,
            kosha_version=__version__,
            content_snapshot=new_snap.sha256,
        )
        save_sync_state(state_path, new_state)
        print(f"Kosha sync {args.sync_command}: surfaces updated.")
    else:
        print(f"Kosha sync {args.sync_command}: no changes written.")
        
    return 0


def _run_sync_agent_fragment(args: argparse.Namespace) -> int:
    import json

    from kosha.sync.agent_fragment import update_instructions

    content = ""
    if args.target.exists():
        content = args.target.read_text("utf-8")

    new_content = update_instructions(content)
    changed = new_content != content

    if changed:
        args.target.parent.mkdir(parents=True, exist_ok=True)
        args.target.write_text(new_content, "utf-8")
        msg = f"Updated {args.target}"
    else:
        msg = f"Already up to date: {args.target}"

    if args.json:
        print(json.dumps({"target": str(args.target), "changed": changed}))
    else:
        print(msg)

    return 0


def _run_review_queue(args: argparse.Namespace) -> int:
    if args.queue_command is None:
        print("kosha: review-queue requires a subcommand: list or decide", file=sys.stderr)
        return 2
    queue = ReviewQueue(args.queue)
    if args.queue_command == "list":
        for item in queue.items():
            print(
                f"{item.item_id}\t{item.status}\t{item.path}\t"
                f"{item.source}\t{len(item.decisions)} decision(s)"
            )
        return 0
    if args.queue_command == "decide":
        try:
            item = queue.record_decision(args.item_id, args.reviewer, args.decision)
        except (KeyError, ValueError) as exc:
            print(f"kosha: review queue decision failed: {exc}", file=sys.stderr)
            return 2
        print(
            f"recorded {item.status} for {item.item_id}; "
            "rerun ingest with explicit approval to apply bundle changes."
        )
        return 0
    print("kosha: review-queue requires a subcommand: list or decide", file=sys.stderr)
    return 2


def _run_serve(args: argparse.Namespace) -> int:
    """Run ``kosha serve``: local HTTP/SSE traversal boundary."""
    clearance = set(resolve_clearance(os.environ))
    clearance.update(label for label in args.clearance if label)
    if not args.allow_non_loopback and not _is_loopback_host(args.host):
        print(
            "kosha: refusing to bind served mode outside loopback without --allow-non-loopback",
            file=sys.stderr,
        )
        return 2
    if args.bundles_dir is not None:
        if not args.bundles_dir.is_dir():
            print(f"kosha: not a bundles directory: {args.bundles_dir}", file=sys.stderr)
            return 2
        access_by_bundle = _parse_bundle_access_map(args.bundle_access)
        missing_access = _bundles_missing_access(args.bundles_dir, access_by_bundle)
        if missing_access and not args.allow_open_bundles:
            print(
                "kosha: refusing to serve bundle(s) without access labels: "
                + ", ".join(missing_access),
                file=sys.stderr,
            )
            return 2
        try:
            registry = build_bundles_dir_registry(
                args.bundles_dir,
                access_by_bundle=access_by_bundle,
                clearance=clearance,
            )
        except ValueError as exc:
            print(f"kosha: {exc}", file=sys.stderr)
            return 2
    else:
        if not args.bundle.is_dir():
            print(f"kosha: not a bundle directory: {args.bundle}", file=sys.stderr)
            return 2
        try:
            registry = build_single_bundle_registry(
                args.bundle,
                bundle_id=args.bundle_id,
                bundle_access=_parse_single_bundle_access(args.bundle_access, args.bundle_id),
                clearance=clearance,
            )
        except ValueError as exc:
            print(f"kosha: {exc}", file=sys.stderr)
            return 2
    with make_http_server(args.host, args.port, registry) as server:
        if args.once:
            print(
                f"serving {len(registry.bundle_ids())} bundle(s) on "
                f"http://{args.host}:{server.server_port}"
            )
            return 0
        print(f"serving traversal boundary on http://{args.host}:{server.server_port}")
        server.serve_forever()
    return 0


def _parse_bundle_access_map(entries: list[str]) -> dict[str, str]:
    access: dict[str, str] = {}
    for entry in entries:
        bundle_id, separator, label = entry.partition("=")
        bundle_id = bundle_id.strip()
        label = label.strip()
        if not separator or not bundle_id or not label:
            raise SystemExit("kosha: --bundle-access for --bundles-dir must be bundle_id=label")
        if bundle_id in access:
            raise SystemExit(f"kosha: duplicate --bundle-access for bundle {bundle_id!r}")
        access[bundle_id] = label
    return access


def _parse_single_bundle_access(entries: list[str], bundle_id: str) -> str | None:
    configured = resolve_bundle_access(os.environ)
    for entry in entries:
        left, separator, right = entry.partition("=")
        if separator:
            supplied_id = left.strip()
            label = right.strip()
            if supplied_id != bundle_id:
                raise SystemExit(
                    f"kosha: --bundle-access targets {supplied_id!r}, "
                    f"but --bundle-id is {bundle_id!r}"
                )
            if not label:
                raise SystemExit("kosha: --bundle-access label must not be blank")
            configured = label
        else:
            label = entry.strip()
            if not label:
                raise SystemExit("kosha: --bundle-access label must not be blank")
            configured = label
    return configured


def _bundles_missing_access(bundles_dir: Path, access_by_bundle: dict[str, str]) -> list[str]:
    child_ids = {path.name for path in bundles_dir.iterdir() if path.is_dir()}
    return sorted(child_ids - set(access_by_bundle))


def _is_loopback_host(host: str) -> bool:
    return host in {"127.0.0.1", "::1", "localhost"}


def _run_watch_ingest(args: argparse.Namespace) -> int:
    """Run guarded scheduled ingest for a finite run count or until interrupted."""
    if args.runs < 0:
        print("kosha: --runs must be 0 or greater", file=sys.stderr)
        return 2
    if args.interval_seconds <= 0:
        print("kosha: --interval-seconds must be greater than 0", file=sys.stderr)
        return 2
    if not args.bundle.is_dir():
        print(f"kosha: not a bundle directory: {args.bundle}", file=sys.stderr)
        return 2
    source = args.source if _is_http_url(args.source) else Path(args.source)
    if isinstance(source, Path) and not source.is_dir():
        print(f"kosha: not a source directory: {source}", file=sys.stderr)
        return 2
    scheduler = ScheduledIngest(
        source,
        args.bundle,
        SourcePolicy(
            max_bytes=args.url_max_bytes,
            allowed_hosts=frozenset(args.allowed_host),
        ),
        interval_seconds=args.interval_seconds,
        reviewer=args.reviewer,
        dry_run=args.dry_run,
        assume_yes=args.yes,
        authority=args.authority,
    )
    queued = 0
    run_count = 0
    while args.runs == 0 or run_count < args.runs:
        try:
            result = scheduler.run_once()
            queued += _enqueue_blocked_if_requested(args, result, str(args.source))
        except (UrlIngestError, ValueError) as exc:
            print(f"kosha: scheduled ingest failed: {exc}", file=sys.stderr)
            return 2
        run_count += 1
        if args.json:
            print(cli_json.dumps(cli_json.ingest_json(result, dry_run=args.dry_run)))
        else:
            print(render_plan(result.plan))
            print()
            print(render_routing(result.routing))
            if args.dry_run:
                print("\ndry run: no changes written. review queue not written.")
        if args.runs == 0 or run_count < args.runs:
            time.sleep(args.interval_seconds)
    if queued and not args.json:
        print(f"\nqueued {queued} BLOCK-lane item(s) for shared review.")
    return 0


def _is_http_url(value: str) -> bool:
    return urlsplit(value).scheme.lower() in {"http", "https"}


def _enqueue_blocked_if_requested(
    args: argparse.Namespace, result: IngestResult, source: str
) -> int:
    if args.review_queue is None:
        return 0
    if args.dry_run:
        return 0
    queue = ReviewQueue(args.review_queue)
    items = queue.enqueue(
        result.plan,
        result.routing,
        source=source,
        created_by=args.reviewer,
    )
    return len(items)


def _run_ingest(args: argparse.Namespace) -> int:
    """Run ``kosha ingest``: build the plan, route it, and commit on approval."""
    if args.watch:
        return _run_watch_ingest(args)
    source = Path(args.source)
    if not source.is_dir():
        print(f"kosha: not a source directory: {source}", file=sys.stderr)
        return 2
    if not args.bundle.is_dir():
        print(f"kosha: not a bundle directory: {args.bundle}", file=sys.stderr)
        return 2
    if args.review and not args.dry_run:
        return _run_ingest_review(args)
    reader = input if sys.stdin.isatty() and not args.yes else None
    try:
        reviewer = normalize_reviewer(args.reviewer)
    except ValueError as exc:
        print(f"kosha: invalid --reviewer: {exc}", file=sys.stderr)
        return 2
    result = ingest(
        source,
        args.bundle,
        asof=datetime.now(UTC),
        source_authority=args.authority,
        dry_run=args.dry_run,
        assume_yes=args.yes,
        reader=reader,
        reviewer=reviewer,
    )
    queued = _enqueue_blocked_if_requested(args, result, str(source))
    if args.json:
        print(cli_json.dumps(cli_json.ingest_json(result, dry_run=args.dry_run)))
        return 0
    print(render_plan(result.plan))
    print()
    print(render_routing(result.routing))
    if args.dry_run:
        print("\ndry run: no changes written. review queue not written.")
        return 0
    if result.committed and result.commit_sha is not None:
        print(
            f"\ncommitted {result.commit_sha[:8]} on {result.branch} (backup {result.backup_tag})."
        )
    else:
        print("\nnot approved: nothing committed.")
    if queued:
        print(f"\nqueued {queued} BLOCK-lane item(s) for shared review.")
    return 0


def _run_ingest_review(args: argparse.Namespace) -> int:
    """Run ``kosha ingest --review``: approve or reject each plan item individually."""
    try:
        reviewer = normalize_reviewer(args.reviewer)
    except ValueError as exc:
        print(f"kosha: invalid --reviewer: {exc}", file=sys.stderr)
        return 2
    source = Path(args.source)
    asof = datetime.now(UTC)
    dry_result = ingest(
        source, args.bundle, asof=asof, source_authority=args.authority, dry_run=True
    )
    if dry_result.plan.is_empty:
        if args.json:
            print(cli_json.dumps(cli_json.ingest_json(dry_result, dry_run=False)))
        else:
            print(render_plan(dry_result.plan))
        return 0
    reader: Reader = input if sys.stdin.isatty() else (lambda _prompt: "")
    printer = (lambda _line: None) if args.json else print
    review = request_item_decisions(dry_result.plan, dry_result.routing, reader, printer=printer)
    approved = review.approved_paths()
    filtered_plan = build_plan([c for c in dry_result.plan.changes if c.path in approved])
    filtered_routing = PlanRouting(
        routes=tuple(r for r in dry_result.routing.routes if r.change.path in approved)
    )
    result = commit_reviewed_plan(
        filtered_plan,
        filtered_routing,
        args.bundle,
        asof=asof,
        source=source,
        reviewer=reviewer,
        evidence_run=dry_result.evidence_run,
    )
    if args.json:
        payload = cli_json.ingest_json(result, dry_run=False)
        payload["review"] = {
            path: decision.value for path, decision in review.change_decisions.items()
        }
        payload["flags_acknowledged"] = review.flags_acknowledged
        print(cli_json.dumps(payload))
        return 0
    print(render_plan(filtered_plan))
    print()
    print(render_routing(filtered_routing))
    if not review.flags_acknowledged:
        print("\nnot approved: an escalated conflict was not acknowledged; nothing committed.")
    elif result.committed and result.commit_sha is not None:
        print(
            f"\ncommitted {result.commit_sha[:8]} on {result.branch} (backup {result.backup_tag})."
        )
    else:
        print("\nnot approved: nothing committed.")
    return 0


def _run_export(args: argparse.Namespace) -> int:
    """Run ``kosha export``: reconstruct and print/write the compliance evidence."""
    if not args.bundle.is_dir():
        print(f"kosha: not a bundle directory: {args.bundle}", file=sys.stderr)
        return 2
    try:
        require_export_access(resolve_bundle_access(os.environ), resolve_clearance(os.environ))
    except AccessDeniedError as exc:
        print(f"kosha: access denied: {exc}", file=sys.stderr)
        return 3
    report = build_report(args.bundle, ref=args.ref, include_source_text=args.include_source_text)
    rendered = (
        to_markdown(report) if args.format == "markdown" else json.dumps(to_json(report), indent=2)
    )
    if args.out is not None:
        args.out.write_text(rendered, encoding="utf-8")
        print(f"Wrote compliance export to {args.out}")
    else:
        print(rendered)
    return 0


def _run_evidence(args: argparse.Namespace) -> int:
    """Run ``kosha evidence`` subcommands."""
    if args.evidence_command == "verify":
        return _run_evidence_verify(args)
    if args.evidence_command == "show":
        return _run_evidence_show(args)
    if args.evidence_command == "replay":
        return _run_evidence_replay(args)
    print(
        "kosha: evidence requires a subcommand: verify, show, replay",
        file=sys.stderr,
    )
    return 2


def _run_evidence_verify(args: argparse.Namespace) -> int:
    """Run ``kosha evidence verify``: check every stored manifest, object, and trailer."""
    if not args.bundle.is_dir():
        print(f"kosha: not a bundle directory: {args.bundle}", file=sys.stderr)
        return 2
    report = verify_evidence(args.bundle, ref=args.ref)
    if args.json:
        print(cli_json.dumps(cli_json.evidence_verify_json(report)))
        return 0 if report.ok else 1
    print(render_verification_text(report))
    return 0 if report.ok else 1


def _run_evidence_show(args: argparse.Namespace) -> int:
    """Run ``kosha evidence show``: metadata-only by default, body only with ``--content``."""
    if not args.bundle.is_dir():
        print(f"kosha: not a bundle directory: {args.bundle}", file=sys.stderr)
        return 2
    vault = EvidenceStore(evidence_root(args.bundle))
    try:
        run = vault.read_run(args.run_id)
        texts = (
            {document.sha256: vault.read_object(document.sha256) for document in run.evidence}
            if args.content
            else None
        )
    except EvidenceCorruptionError as exc:
        print(f"kosha: evidence corruption: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(cli_json.dumps(cli_json.evidence_show_json(run, texts)))
        return 0
    print(_render_evidence_show_text(run, texts))
    return 0


def _render_evidence_show_text(run: SourceRun, texts: dict[str, str] | None) -> str:
    lines = [
        f"Source run {run.run_id}",
        f"  bundle_identity:    {run.bundle_identity}",
        f"  source_instance_id: {run.source_instance_id}",
        f"  adapter:            {run.adapter} (v{run.adapter_version})",
        f"  started_at:         {run.started_at.isoformat()}",
        f"  completed_at:       {run.completed_at.isoformat()}",
        f"  status:             {run.status.value}",
    ]
    if run.detector_names:
        lines.append(f"  detector_names:     {', '.join(run.detector_names)}")
    lines.append(f"  evidence documents: {len(run.evidence)}")
    for document in run.evidence:
        lines.append(f"    - {document.sha256}")
        lines.append(f"      source_id: {document.source_id}")
        lines.append(f"      location:  {document.location}")
        lines.append(
            f"      bytes:     {document.normalized_text_bytes} "
            f"(normalization v{document.normalization_version})"
        )
        if texts is not None:
            lines.append("      content:")
            lines.extend(f"        {line}" for line in texts[document.sha256].splitlines())
    return "\n".join(lines)


def _run_evidence_replay(args: argparse.Namespace) -> int:
    """Run ``kosha evidence replay``: zero-network dry run against stored evidence."""
    if not args.bundle.is_dir():
        print(f"kosha: not a bundle directory: {args.bundle}", file=sys.stderr)
        return 2
    try:
        report = replay_run(args.bundle, args.run_id, ref=args.ref)
    except EvidenceCorruptionError as exc:
        print(f"kosha: evidence corruption: {exc}", file=sys.stderr)
        return 1
    except ReplayError as exc:
        print(f"kosha: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(cli_json.dumps(cli_json.evidence_replay_json(report)))
        return 0
    print(render_replay_text(report))
    return 0


def _run_validate(bundle: Path, json_output: bool = False) -> int:
    """Validate ``bundle`` and return a process exit code (0 = conformant)."""
    if not bundle.is_dir():
        print(f"kosha: not a bundle directory: {bundle}", file=sys.stderr)
        return 2
    report = validate_bundle(bundle)
    if json_output:
        print(cli_json.dumps(cli_json.validate_json(bundle, report)))
        return 1 if report.errors else 0
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
    print(f"Wrote {stats.concept_count} concepts across {stats.module_count} modules to {out_dir}")
    return 0


def _run_bench_realworld(args: argparse.Namespace) -> int:
    """Run the real-world benchmark and record the go/no-go verdict."""
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
        fidelity_targeter=args.fidelity_targeter,
    )

    def _progress(message: str) -> None:
        print(f"[realworld] {message}", file=sys.stderr, flush=True)

    embedding_provider = resolve_embedding_provider()
    generation_provider = resolve_generation_provider()
    mismatch = default_threshold_mismatch(embedding_provider, DEFAULT_THRESHOLDS)
    if mismatch is not None:
        print(f"kosha: warning: {mismatch}", file=sys.stderr)
    local_warning = local_provider_gate_warning(
        embedding_provider.name, generation_provider.name, config.ingests
    )
    if local_warning is not None:
        print(f"kosha: warning: {local_warning}", file=sys.stderr)
    report = run_realworld(
        config,
        embedding_provider,
        generation_provider,
        progress=_progress,
    )
    if args.json:
        print(cli_json.dumps(cli_json.bench_realworld_json(args.corpus, report)))
    else:
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
        if not args.json:
            print(f"Wrote report to {args.report}")
    return 0


def _run_calibrate(args: argparse.Namespace) -> int:
    """Fit every decision threshold to the configured providers on the seed labels."""
    if not args.labels.is_file():
        print(f"kosha: not a labels file: {args.labels}", file=sys.stderr)
        return 2
    for path in (args.labels, _MERGE_LABELS, _RELATE_LABELS):
        try:
            assert_seed_labels_path(path)
        except ValueError as error:
            print(f"kosha: {error}", file=sys.stderr)
            return 2
    pairs = load_dedup_pairs(args.labels)
    calibration = calibrate_thresholds(pairs, resolve_embedding_provider(), margin=args.margin)
    adjudicator = calibrate_adjudicator_threshold(pairs)
    targeter = calibrate_targeter_threshold(load_merge_cases(_MERGE_LABELS))
    relator = calibrate_relator_threshold(load_relate_cases(_RELATE_LABELS))
    if args.json:
        print(cli_json.dumps(cli_json.calibrate_json(calibration, adjudicator, targeter, relator)))
        return 0
    print(render_calibration(calibration))
    print(render_single_threshold_calibration(adjudicator))
    print(render_single_threshold_calibration(targeter))
    print(render_single_threshold_calibration(relator))
    return 0


def _run_bench(bundle_path: Path, report_path: Path | None, json_output: bool = False) -> int:
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
    if json_output:
        payload = cli_json.bench_json(bundle_path, report, dedup, kill_signals, verdict)
        print(cli_json.dumps(payload))
    else:
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
        if not json_output:
            print(f"Wrote report to {report_path}")
    return 0


def _run_bench_acceptance(
    bundle_path: Path, report_path: Path | None, json_output: bool = False
) -> int:
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
    if json_output:
        print(cli_json.dumps(cli_json.bench_acceptance_json(bundle_path, report)))
    else:
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
        if not json_output:
            print(f"Wrote report to {report_path}")
    return 0 if report.passed else 1


def _run_eval(args: argparse.Namespace) -> int:
    """Dispatch ``kosha eval <suite>``."""
    if args.eval_command == "extract":
        return _run_eval_extract(args.labels, args.json)
    if args.eval_command == "dedup":
        return _run_eval_dedup(args.labels, args.bundle, args.json)
    if args.eval_command == "merge":
        return _run_eval_merge(args.labels, args.json)
    if args.eval_command == "relate":
        return _run_eval_relate(args.labels, args.json)
    if args.eval_command == "contradict":
        return _run_eval_contradict(args.labels, args.json)
    print("kosha: usage: kosha eval {extract,dedup,merge,relate,contradict} [...]", file=sys.stderr)
    return 2


def _run_eval_extract(labels_path: Path, json_output: bool = False) -> int:
    """Score the concept extractor against the seed granularity labels."""
    if not labels_path.is_file():
        print(f"kosha: labels file not found: {labels_path}", file=sys.stderr)
        return 2
    provider = resolve_generation_provider()
    report = evaluate_extractor(load_granularity_labels(labels_path), provider)
    if json_output:
        print(cli_json.dumps(cli_json.eval_extract_json(labels_path, provider.name, report)))
        return 0
    print(f"Extractor eval over {labels_path} ({report.label_count} labels, gen={provider.name})")
    print(f"boundary accuracy: {report.score:.3f} ({report.correct}/{report.label_count})")
    return 0


def _run_eval_dedup(labels_path: Path, bundle_path: Path, json_output: bool = False) -> int:
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
    if json_output:
        print(
            cli_json.dumps(
                cli_json.eval_dedup_json(
                    labels_path,
                    bundle_path,
                    embedding_provider.name,
                    adjudicator.name,
                    report,
                    duplicates,
                )
            )
        )
        return 0
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


def _run_eval_merge(labels_path: Path, json_output: bool = False) -> int:
    """Score the merge surface's claim-targeting accuracy against seed cases."""
    if not labels_path.is_file():
        print(f"kosha: labels file not found: {labels_path}", file=sys.stderr)
        return 2
    targeter = LexicalClaimTargeter()
    report = evaluate_merge(load_merge_cases(labels_path), targeter)
    if json_output:
        print(cli_json.dumps(cli_json.eval_merge_json(labels_path, targeter.name, report)))
        return 0
    print(f"Merge eval over {labels_path} ({report.case_count} cases, targeter={targeter.name})")
    print(f"targeting accuracy: {report.score:.3f} ({report.correct}/{report.case_count})")
    return 0


def _run_eval_relate(labels_path: Path, json_output: bool = False) -> int:
    """Score the cross-linker relate surface: link-discovery precision/recall/F1."""
    if not labels_path.is_file():
        print(f"kosha: labels file not found: {labels_path}", file=sys.stderr)
        return 2
    relator = LexicalRelator()
    report = evaluate_relate(load_relate_cases(labels_path), relator)
    if json_output:
        print(cli_json.dumps(cli_json.eval_relate_json(labels_path, relator.name, report)))
        return 0
    print(f"Relate eval over {labels_path} ({report.case_count} cases, relator={relator.name})")
    print(
        f"precision: {report.precision:.3f}  recall: {report.recall:.3f}  f1: {report.f1:.3f} "
        f"({report.true_positives}/{report.gold_total} gold edges)"
    )
    return 0


def _run_eval_contradict(labels_path: Path, json_output: bool = False) -> int:
    """Score the contradiction detector: conflict-detection precision/recall/F1."""
    if not labels_path.is_file():
        print(f"kosha: labels file not found: {labels_path}", file=sys.stderr)
        return 2
    judge = LexicalContradictionJudge()
    cases = load_contradict_cases(labels_path)
    report = evaluate_contradict(cases, judge)
    by_regime = evaluate_contradict_by_regime(cases, judge)
    if json_output:
        payload = cli_json.eval_contradict_json(labels_path, judge.name, report, by_regime)
        print(cli_json.dumps(payload))
        return 0
    print(f"Contradict eval over {labels_path} ({report.case_count} cases, judge={judge.name})")
    print(
        f"precision: {report.precision:.3f}  recall: {report.recall:.3f}  "
        f"f1: {report.f1:.3f}  accuracy: {report.accuracy:.3f}"
    )
    for regime, regime_report in by_regime.items():
        print(
            f"  regime={regime:<12} precision: {regime_report.precision:.3f}  "
            f"recall: {regime_report.recall:.3f}  f1: {regime_report.f1:.3f}  "
            f"({regime_report.case_count} cases)"
        )
    return 0


def _run_recover(args: argparse.Namespace) -> int:
    """Dispatch ``kosha recover <backups|restore|reindex>``."""
    if getattr(args, "recover_command", None) is None:
        print("kosha: usage: kosha recover {backups,restore,reindex} [...]", file=sys.stderr)
        return 2
    if not args.bundle.is_dir():
        print(f"kosha: not a bundle directory: {args.bundle}", file=sys.stderr)
        return 2
    store = GitStore(args.bundle)
    if not store.is_repo():
        print(f"kosha: not a git repository: {args.bundle}", file=sys.stderr)
        return 2
    if args.recover_command == "backups":
        return _run_recover_backups(args, store)
    if args.recover_command == "restore":
        return _run_recover_restore(args, store)
    return _run_recover_reindex(args, store)


def _run_recover_backups(args: argparse.Namespace, store: GitStore) -> int:
    """Run ``kosha recover backups``: list every ``backup/<date>`` tag."""
    backups = list_backups(store)
    if args.json:
        print(cli_json.dumps(cli_json.recover_backups_json(args.bundle, backups)))
        return 0
    if not backups:
        print("No backup tags found.")
        return 0
    for backup in backups:
        print(f"{backup.name}  {backup.sha[:8]}")
    return 0


def _run_recover_restore(args: argparse.Namespace, store: GitStore) -> int:
    """Run ``kosha recover restore``: dry-run by default, mutate only with ``--apply``."""
    try:
        plan = describe_restore(store, args.tag)
    except RecoveryError as exc:
        print(f"kosha: {exc}", file=sys.stderr)
        return 2
    record = None
    if args.apply:
        record = apply_restore(store, plan, branch=args.branch)
        if args.audit_log is not None:
            append_audit_log(args.audit_log, record)
    if args.json:
        print(cli_json.dumps(cli_json.recover_restore_json(args.bundle, plan, record)))
        return 0
    print(f"Restore plan: {plan.tag} -> {plan.ref[:8]}")
    if plan.is_empty:
        print("No differences: nothing to restore.")
        return 0
    for change in plan.changes:
        print(f"  {change.status} {change.path}")
    if record is None:
        print(
            f"\ndry run: no changes written. "
            f"Re-run with --apply to restore {len(plan.changes)} file(s)."
        )
        return 0
    print(
        f"\nrestored {len(plan.changes)} file(s) on {record.branch} "
        f"(commit {(record.commit_sha or '')[:8]}, backup {record.backup_tag})."
    )
    return 0


def _run_recover_reindex(args: argparse.Namespace, store: GitStore) -> int:
    """Run ``kosha recover reindex``: dry-run by default, mutate only with ``--apply``."""
    plan = describe_reindex(args.bundle)
    record = None
    if args.apply:
        record = apply_reindex(store, args.bundle, plan, branch=args.branch)
        if args.audit_log is not None:
            append_audit_log(args.audit_log, record)
    if args.json:
        print(cli_json.dumps(cli_json.recover_reindex_json(args.bundle, plan, record)))
        return 0
    if plan.is_empty:
        print("No drift: every index.md already matches the bundle's concepts.")
        return 0
    for change in plan.changes:
        print(f"  {change.action} {change.path}")
    if record is None:
        print(
            f"\ndry run: no changes written. "
            f"Re-run with --apply to reindex {len(plan.changes)} file(s)."
        )
        return 0
    print(
        f"\nreindexed {len(plan.changes)} file(s) on {record.branch} "
        f"(commit {(record.commit_sha or '')[:8]}, backup {record.backup_tag})."
    )
    return 0


def _run_release(args: argparse.Namespace) -> int:
    """Run ``kosha release``: validate, tag, and optionally export a bundle release."""
    if not args.bundle.is_dir():
        print(f"kosha: not a bundle directory: {args.bundle}", file=sys.stderr)
        return 2
    store = GitStore(args.bundle)
    if not store.is_repo():
        print(f"kosha: not a git repository: {args.bundle}", file=sys.stderr)
        return 2
    export_path = args.out.resolve() if args.out is not None else None
    try:
        record = create_release(store, args.bundle, args.tag, export_path=export_path)
    except ReleaseError as exc:
        print(f"kosha: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(cli_json.dumps(cli_json.release_json(args.bundle, record)))
        return 0
    print(
        f"Released {record.tag} -> {record.ref[:8]} "
        f"({record.concept_count} concepts, {record.warning_count} warning(s))"
    )
    if record.export_path is not None:
        print(f"Exported to {record.export_path}")
    return 0


def _max_depth(concept_ids: Iterable[str]) -> int:
    """Return the deepest concept path depth (segments) in the bundle."""
    return max((cid.count("/") + 1 for cid in concept_ids), default=0)


if __name__ == "__main__":
    raise SystemExit(main())

def _run_doctor_providers(args: argparse.Namespace) -> int:
    embed_diag = diagnose_embedding_provider()
    gen_diag = diagnose_generation_provider()
    
    print("Provider Diagnostics")
    print("====================")
    
    has_errors = False
    
    for diag in [embed_diag, gen_diag]:
        print(f"\n[{diag.role.capitalize()} Provider]")
        print(f"Configured: {diag.is_configured}")
        print(f"Source:     {diag.source}")
        print(f"Identity:   {diag.provider_name}")
        
        if diag.vars:
            print("\nEnvironment Variables:")
            for var in diag.vars:
                status = var.preview if var.is_set else "(unset)"
                if var.suspicious:
                    status += f" [WARNING: {', '.join(var.suspicious)}]"
                print(f"  {var.key}: {status}")
                
        if diag.errors:
            has_errors = True
            print("\nErrors:")
            for err in diag.errors:
                print(f"  - {err}")

    return 1 if has_errors else 0
