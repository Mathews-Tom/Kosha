"""The auditability / guarantee acceptance axis (spike S2, Track D)."""

from __future__ import annotations

from pathlib import Path

from kosha.bench.gate2.auditability import (
    AuditabilityResult,
    run_auditability,
    verify_branch_per_ingest,
    verify_guarantee,
    verify_supersede_lineage,
)
from kosha.bench.gate2.contradictions import load_contradictions

ROOT = Path(__file__).resolve().parents[2]
COMMITTED = ROOT / "evals" / "realworld" / "contradictions_v2.jsonl"


def test_guarantee_never_silently_overwrites_on_the_held_out_set() -> None:
    cases = load_contradictions(COMMITTED)
    checked, violations = verify_guarantee(cases)
    assert checked == len(cases)
    assert violations == 0


def test_supersede_lineage_retains_the_retired_ancestor() -> None:
    assert verify_supersede_lineage() is True


def test_branch_per_ingest_gates_the_update_and_preserves_main(tmp_path: Path) -> None:
    assert verify_branch_per_ingest(tmp_path) is True


def test_run_auditability_verifies_the_loop_end_to_end(tmp_path: Path) -> None:
    cases = load_contradictions(COMMITTED)
    result = run_auditability(cases, work_dir=tmp_path)
    assert isinstance(result, AuditabilityResult)
    assert result.guarantee_verified
    assert result.provenance_replayable
    assert result.verified
    assert result.guarantee_cases == len(cases)
    assert result.guarantee_violations == 0


def test_empty_case_set_is_not_a_verified_guarantee() -> None:
    result = AuditabilityResult(
        guarantee_cases=0,
        guarantee_violations=0,
        supersede_lineage_ok=True,
        branch_per_ingest_ok=True,
    )
    assert not result.guarantee_verified
    assert not result.verified


def test_a_provenance_gap_is_not_replayable() -> None:
    result = AuditabilityResult(
        guarantee_cases=108,
        guarantee_violations=0,
        supersede_lineage_ok=True,
        branch_per_ingest_ok=False,
    )
    assert result.guarantee_verified
    assert not result.provenance_replayable
    assert not result.verified
