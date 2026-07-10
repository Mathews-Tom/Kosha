"""Acceptance harness — the token/latency MVP success criterion (M12 PR-1).

The token gate proves the hybrid win two ways: strictly fewer tokens than the
raw-docs baseline, and fewer tokens than RAG *per unit of answer quality* (a
raw-token race rewards a strategy that answers less). The latency gate uses the
deterministic round-trip comparison and only lets wall-clock contribute above the
noise floor, so it never flakes on local compute.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kosha.bench.acceptance import (
    AcceptanceCriterion,
    AcceptanceReport,
    ContradictionSafetyReport,
    FidelityReport,
    contradiction_criterion,
    deep_latency_criterion,
    duplicate_rate_criterion,
    fidelity_criterion,
    measure_contradiction_safety,
    measure_deep_latency,
    measure_fidelity,
    render_acceptance_report,
    run_acceptance,
    token_latency_criterion,
)
from kosha.bench.runner import BenchReport, StrategyResult
from kosha.cli import main
from kosha.dedup import LexicalAdjudicator
from kosha.eval.dedup import DuplicateRateReport, evaluate_duplicate_rate
from kosha.merge import LexicalClaimTargeter
from kosha.okf import load_bundle
from kosha.providers import ExtractiveGenerationProvider, LexicalEmbeddingProvider
from kosha.providers.base import Generation, Usage

ROOT = Path(__file__).resolve().parents[2]
NORTHWIND = ROOT / "bundles" / "northwind"


def _strategy(
    name: str,
    *,
    total_tokens: float,
    recall: float,
    round_trips: float = 2.0,
    latency_ms: float = 0.3,
) -> StrategyResult:
    return StrategyResult(
        name=name,
        avg_context_tokens=total_tokens * 0.8,
        avg_total_tokens=total_tokens,
        avg_round_trips=round_trips,
        avg_latency_ms=latency_ms,
        concept_recall=recall,
        keyword_recall=recall,
        answered_fraction=1.0,
    )


class _FirstClaimProvider:
    @property
    def name(self) -> str:
        return "first-claim"

    def generate(self, query: str, context: str) -> Generation:
        del query, context
        return Generation("1", Usage(prompt_tokens=1, completion_tokens=1))


def _bench(*results: StrategyResult) -> BenchReport:
    return BenchReport(
        embedding_provider="test-embed",
        generation_provider="test-gen",
        query_count=8,
        results=results,
    )


def test_token_latency_criterion_passes_on_northwind() -> None:
    bundle = load_bundle(NORTHWIND)
    report = run_acceptance(
        bundle,
        LexicalEmbeddingProvider(),
        ExtractiveGenerationProvider(),
        bundle_path=str(NORTHWIND),
    )
    criterion = report.by_id("C1-token-latency")
    assert criterion.passed
    assert report.passed


def test_token_win_is_measured_at_matched_quality() -> None:
    # Hybrid spends MORE raw tokens than RAG but achieves full recall where RAG
    # answers a fraction; per-recall, hybrid is cheaper, so the criterion passes.
    bench = _bench(
        _strategy("hybrid", total_tokens=600, recall=1.0),
        _strategy("rag", total_tokens=500, recall=0.6),
        _strategy("long_context", total_tokens=1100, recall=1.0, round_trips=1.0),
    )
    criterion = token_latency_criterion(bench)
    assert criterion.passed


def test_token_criterion_fails_when_hybrid_loses_to_rag_at_equal_quality() -> None:
    bench = _bench(
        _strategy("hybrid", total_tokens=900, recall=1.0),
        _strategy("rag", total_tokens=500, recall=1.0),
        _strategy("long_context", total_tokens=1100, recall=1.0, round_trips=1.0),
    )
    criterion = token_latency_criterion(bench)
    assert not criterion.passed


def test_token_criterion_fails_when_hybrid_costs_more_than_raw_docs() -> None:
    bench = _bench(
        _strategy("hybrid", total_tokens=1200, recall=1.0),
        _strategy("rag", total_tokens=2000, recall=0.5),
        _strategy("long_context", total_tokens=1100, recall=1.0, round_trips=1.0),
    )
    criterion = token_latency_criterion(bench)
    assert not criterion.passed


def test_latency_criterion_fails_on_extra_round_trips() -> None:
    bench = _bench(
        _strategy("hybrid", total_tokens=400, recall=1.0, round_trips=3.0),
        _strategy("rag", total_tokens=500, recall=0.6, round_trips=2.0),
        _strategy("long_context", total_tokens=1100, recall=1.0, round_trips=1.0),
    )
    criterion = token_latency_criterion(bench)
    assert not criterion.passed


def test_latency_criterion_uses_wallclock_above_the_noise_floor() -> None:
    # Above the noise floor a 3x slower hybrid blows the margin; within it passes.
    blown = _bench(
        _strategy("hybrid", total_tokens=400, recall=1.0, latency_ms=30.0),
        _strategy("rag", total_tokens=500, recall=0.6, latency_ms=10.0),
        _strategy("long_context", total_tokens=1100, recall=1.0, round_trips=1.0),
    )
    assert not token_latency_criterion(blown).passed

    within = _bench(
        _strategy("hybrid", total_tokens=400, recall=1.0, latency_ms=15.0),
        _strategy("rag", total_tokens=500, recall=0.6, latency_ms=10.0),
        _strategy("long_context", total_tokens=1100, recall=1.0, round_trips=1.0),
    )
    assert token_latency_criterion(within).passed


def test_deep_latency_criterion_measures_depth_five_bundle() -> None:
    report = measure_deep_latency(
        LexicalEmbeddingProvider(),
        ExtractiveGenerationProvider(),
    )
    criterion = deep_latency_criterion(report)

    assert report.depth == 5
    assert criterion.id == "C2-deep-latency"
    assert criterion.passed
    assert "depth 5" in criterion.evidence


def test_report_passes_iff_every_criterion_passes() -> None:
    ok = AcceptanceCriterion("X", "ok", passed=True, target="t", evidence="e")
    bad = AcceptanceCriterion("Y", "bad", passed=False, target="t", evidence="e")
    passing = AcceptanceReport("b", 1, "em", "gen", (ok,))
    failing = AcceptanceReport("b", 1, "em", "gen", (ok, bad))
    assert passing.passed
    assert not failing.passed


def test_run_acceptance_verdicts_are_deterministic() -> None:
    # Token + recall figures are deterministic; only wall-clock latency is not, so
    # the stable invariant is the per-criterion pass/fail verdict, not the bytes.
    bundle = load_bundle(NORTHWIND)
    first = run_acceptance(
        bundle, LexicalEmbeddingProvider(), ExtractiveGenerationProvider(), bundle_path="b"
    )
    second = run_acceptance(
        bundle, LexicalEmbeddingProvider(), ExtractiveGenerationProvider(), bundle_path="b"
    )
    assert [(c.id, c.passed) for c in first.criteria] == [(c.id, c.passed) for c in second.criteria]
    assert first.passed == second.passed


def test_render_acceptance_report_shows_verdict_and_each_criterion() -> None:
    bundle = load_bundle(NORTHWIND)
    report = run_acceptance(
        bundle,
        LexicalEmbeddingProvider(),
        ExtractiveGenerationProvider(),
        bundle_path=str(NORTHWIND),
    )
    document = render_acceptance_report(report)
    assert "# Kosha MVP Acceptance Report" in document
    assert "**Verdict: PASS**" in document
    assert "C1-token-latency" in document


def test_cli_bench_acceptance_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["bench", "acceptance", "--bundle", str(NORTHWIND)])
    out = capsys.readouterr().out
    assert code == 0
    assert "MVP success contract: PASS" in out


def test_cli_bench_acceptance_writes_report(tmp_path: Path) -> None:
    report_path = tmp_path / "ACCEPTANCE_REPORT.md"
    code = main(["bench", "acceptance", "--bundle", str(NORTHWIND), "--report", str(report_path)])
    assert code == 0
    assert report_path.is_file()
    assert "MVP Acceptance Report" in report_path.read_text(encoding="utf-8")


def test_duplicate_rate_criterion_passes_on_northwind() -> None:
    bundle = load_bundle(NORTHWIND)
    duplicates = evaluate_duplicate_rate(
        bundle, LexicalEmbeddingProvider(), adjudicator=LexicalAdjudicator()
    )
    criterion = duplicate_rate_criterion(duplicates)
    assert criterion.passed
    assert duplicates.created == 0


def test_duplicate_rate_criterion_fails_on_any_create() -> None:
    # A single CREATE on a re-ingest is a duplicate the resolver missed.
    duplicates = DuplicateRateReport(concept_count=12, created=1, updated=11)
    assert not duplicate_rate_criterion(duplicates).passed


def test_measure_fidelity_holds_across_20_ingests(tmp_path: Path) -> None:
    report = measure_fidelity(tmp_path)
    assert report.ingests == 20
    assert report.drift_free
    assert report.reconstructable
    assert report.survivor_intact
    assert report.conformant
    assert report.latest_reflected
    assert report.ok


def test_measure_fidelity_runs_with_generation_targeter(tmp_path: Path) -> None:
    report = measure_fidelity(
        tmp_path,
        ingests=20,
        generation_provider=_FirstClaimProvider(),
    )

    assert report.ok
    assert report.targeter_name == "generation:first-claim"
    assert "generation:first-claim" in fidelity_criterion(report).evidence


def test_measure_fidelity_rejects_both_targeter_and_generation_provider(
    tmp_path: Path,
) -> None:
    # M4: the two ways to pick a non-default targeter are mutually exclusive;
    # silently preferring one would hide which targeter a report actually used.
    with pytest.raises(ValueError, match="pass targeter or generation_provider, not both"):
        measure_fidelity(
            tmp_path,
            targeter=LexicalClaimTargeter(),
            generation_provider=_FirstClaimProvider(),
        )


def test_measure_fidelity_manages_its_own_scratch_dir() -> None:
    # Called with no work_dir, the harness still runs the full conformance check.
    report = measure_fidelity(ingests=20)
    assert report.ok


def test_fidelity_criterion_fails_below_the_ingest_threshold() -> None:
    short = FidelityReport(
        ingests=5,
        drift_free=True,
        reconstructable=True,
        survivor_intact=True,
        conformant=True,
        latest_reflected=True,
    )
    assert not fidelity_criterion(short).passed


def test_fidelity_criterion_fails_on_any_drift() -> None:
    drifted = FidelityReport(
        ingests=20,
        drift_free=False,
        reconstructable=True,
        survivor_intact=True,
        conformant=True,
        latest_reflected=True,
    )
    assert not fidelity_criterion(drifted).passed


def test_run_acceptance_gates_all_five_criteria() -> None:
    bundle = load_bundle(NORTHWIND)
    report = run_acceptance(
        bundle,
        LexicalEmbeddingProvider(),
        ExtractiveGenerationProvider(),
        bundle_path=str(NORTHWIND),
    )
    ids = [c.id for c in report.criteria]
    assert ids == [
        "C1-token-latency",
        "C2-deep-latency",
        "C3-duplicate-rate",
        "C4-fidelity",
        "C5-contradiction-safety",
    ]
    assert report.passed


def test_measure_contradiction_safety_handles_every_injected() -> None:
    safety = measure_contradiction_safety()
    # Temporal run (10) + one authority override + one escalation = 12 injected.
    assert safety.injected == 12
    assert safety.conflicting == safety.injected
    assert safety.handled == safety.injected
    assert safety.resolved == 11  # 10 temporal + 1 authority
    assert safety.escalated == 1
    assert safety.silent_overwrites == 0
    assert safety.ok
    assert contradiction_criterion(safety).passed


def test_contradiction_criterion_fails_on_a_silent_overwrite() -> None:
    unsafe = ContradictionSafetyReport(
        injected=12, conflicting=12, resolved=11, escalated=1, silent_overwrites=1
    )
    assert not contradiction_criterion(unsafe).passed


def test_contradiction_criterion_fails_when_a_conflict_is_lost() -> None:
    # A conflict neither resolved nor escalated (handled < injected) is "lost".
    lost = ContradictionSafetyReport(
        injected=12, conflicting=12, resolved=10, escalated=1, silent_overwrites=0
    )
    assert lost.handled == 11
    assert not contradiction_criterion(lost).passed


def test_cli_bench_acceptance_exits_nonzero_when_a_criterion_fails(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # The exit code is the contract gate: a single failing criterion is non-zero.
    from kosha import cli

    failing = AcceptanceReport(
        "b",
        1,
        "em",
        "gen",
        (AcceptanceCriterion("C1", "x", passed=False, target="t", evidence="e"),),
    )
    monkeypatch.setattr(cli, "run_acceptance", lambda *a, **k: failing)
    code = cli.main(["bench", "acceptance", "--bundle", str(NORTHWIND)])
    assert code == 1
    assert "MVP success contract: FAIL" in capsys.readouterr().out
