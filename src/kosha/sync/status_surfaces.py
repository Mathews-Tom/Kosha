"""Check generated README and Gate-0 status surfaces against renderers."""

from __future__ import annotations

import re
from pathlib import Path

from kosha.bench.acceptance import AcceptanceCriterion, AcceptanceReport, run_acceptance
from kosha.bench.realworld.runner import (
    DriftResult,
    MaintenanceResult,
    QueryStrategyResult,
    RealworldReport,
    SafetyResult,
)
from kosha.bench.realworld.status import render_gate_status_summary
from kosha.okf import load_bundle
from kosha.providers import resolve_embedding_provider, resolve_generation_provider
from kosha.sync.check import SyncMismatch

README_PATH = Path("README.md")
GATE0_STATUS_PATH = Path("docs/gate0-status.md")
DEFAULT_ACCEPTANCE_BUNDLE = Path("bundles/northwind")


def check_status_surfaces(repo_root: Path) -> tuple[SyncMismatch, ...]:
    """Return mismatches for deterministic README and Gate-0 status surfaces."""

    mismatches: list[SyncMismatch] = []
    mismatches.extend(check_gate0_status(repo_root))
    mismatches.extend(check_readme_acceptance_table(repo_root))
    return tuple(mismatches)


def check_gate0_status(repo_root: Path) -> tuple[SyncMismatch, ...]:
    """Check that the Gate-0 verdict sentence matches the recorded report renderer."""

    path = repo_root / GATE0_STATUS_PATH
    if not path.is_file():
        return (_missing_file("gate0-status", path),)
    expected = render_gate_status_summary(recorded_gate0_report())
    text = path.read_text(encoding="utf-8")
    if expected in text:
        return ()
    return (
        SyncMismatch(
            surface="gate0-status",
            path=path,
            message="Gate-0 verdict summary does not match the recorded report renderer",
            details=(expected,),
        ),
    )


def check_readme_acceptance_table(repo_root: Path) -> tuple[SyncMismatch, ...]:
    """Check that README's deterministic gate table matches acceptance output."""

    path = repo_root / README_PATH
    if not path.is_file():
        return (_missing_file("readme-acceptance-table", path),)
    expected_rows = render_readme_acceptance_rows(run_default_acceptance_report(repo_root))
    text = path.read_text(encoding="utf-8")
    missing = tuple(row for row in expected_rows if row not in text)
    if not missing:
        return ()
    return (
        SyncMismatch(
            surface="readme-acceptance-table",
            path=path,
            message="README deterministic self-consistency table is stale",
            details=tuple(f"missing row: {row}" for row in missing),
        ),
    )


def run_default_acceptance_report(repo_root: Path) -> AcceptanceReport:
    """Run the deterministic acceptance gate that sources README status rows."""

    bundle_path = repo_root / DEFAULT_ACCEPTANCE_BUNDLE
    bundle = load_bundle(bundle_path)
    return run_acceptance(
        bundle,
        resolve_embedding_provider(),
        resolve_generation_provider(),
        bundle_path=DEFAULT_ACCEPTANCE_BUNDLE.as_posix(),
    )


def render_readme_acceptance_rows(report: AcceptanceReport) -> tuple[str, ...]:
    """Render README status table rows from an acceptance report."""

    return tuple(_readme_acceptance_row(criterion) for criterion in report.criteria)


def recorded_gate0_report() -> RealworldReport:
    """Return the currently recorded Gate-0 report identity for public status docs."""

    return RealworldReport(
        embedding_provider="bge-m3",
        generation_provider="gpt-4o-mini",
        corpus_path="bundles/pydoc-stdlib",
        concept_count=680,
        query_count=0,
        queries=(
            QueryStrategyResult(
                name="hybrid",
                concept_recall=1.0,
                keyword_recall=1.0,
                avg_context_tokens=0.0,
                avg_total_tokens=0.0,
            ),
        ),
        maintenance=(
            MaintenanceResult(name="kosha_loop", correct=5, total=10, by_kind={}),
            MaintenanceResult(name="prompt_only", correct=8, total=10, by_kind={}),
        ),
        drift=DriftResult(
            ingests=50,
            accuracy_start=0.9,
            accuracy_end=0.9,
            fidelity_ok=True,
            seed_concepts=150,
            final_concepts=200,
            fidelity_targeter="lexical",
        ),
        safety=(
            SafetyResult(name="kosha_loop", cases=108, safe=72, silent_overwrites=0),
            SafetyResult(name="prompt_only", cases=108, safe=108, silent_overwrites=0),
        ),
    )


def _readme_acceptance_row(criterion: AcceptanceCriterion) -> str:
    status = "PASS" if criterion.passed else "FAIL"
    summary = _readme_acceptance_summary(criterion)
    return f"| {criterion.name} | **{status}** — {summary} |"


def _readme_acceptance_summary(criterion: AcceptanceCriterion) -> str:
    if criterion.id == "C1-token-latency":
        tokens = _require_match(
            criterion.evidence,
            r"tokens-per-recall: hybrid ([0-9.]+) vs RAG ([0-9.]+)",
            criterion.id,
        )
        recall = _require_match(
            criterion.evidence,
            r"concept recall: hybrid ([0-9.]+) vs RAG ([0-9.]+)",
            criterion.id,
        )
        return (
            f"{tokens[0]} vs {tokens[1]} tokens-per-recall; "
            f"recall {recall[0]} vs {recall[1]}"
        )
    if criterion.id == "C2-deep-latency":
        depth = _require_match(criterion.evidence, r"depth ([0-9]+)", criterion.id)[0]
        tokens = _require_match(
            criterion.evidence,
            r"tokens-per-recall: hybrid ([0-9.]+) vs RAG ([0-9.]+)",
            criterion.id,
        )
        return f"depth {depth}; {tokens[0]} vs {tokens[1]} tokens-per-recall"
    if criterion.id == "C3-duplicate-rate":
        parts = _require_match(
            criterion.evidence,
            r"re-ingesting ([0-9]+) existing concepts: ([0-9]+) CREATE / ([0-9]+) UPDATE",
            criterion.id,
        )
        return (
            f"re-ingesting {parts[0]} concepts -> "
            f"{parts[1]} create / {parts[2]} update"
        )
    if criterion.id == "C4-fidelity":
        ingests = _require_match(
            criterion.evidence, r"([0-9]+) sequential ingests", criterion.id
        )[0]
        return f"no edit-drift across {ingests} sequential ingests"
    if criterion.id == "C5-contradiction-safety":
        handled = _require_match(
            criterion.evidence,
            (
                r"([0-9]+) injected contradictions: [^;]+; "
                r"[^=]+ = ([0-9]+) handled; ([0-9]+) silent overwrites"
            ),
            criterion.id,
        )
        return f"{handled[1]}/{handled[0]} handled; {handled[2]} silent overwrites"
    raise ValueError(f"unsupported acceptance criterion for README sync: {criterion.id}")


def _require_match(text: str, pattern: str, criterion_id: str) -> tuple[str, ...]:
    match = re.search(pattern, text)
    if match is None:
        raise ValueError(f"cannot render README status for {criterion_id}: {text}")
    return match.groups()


def _missing_file(surface: str, path: Path) -> SyncMismatch:
    return SyncMismatch(surface=surface, path=path, message="expected status surface is missing")
