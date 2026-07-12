"""Deterministic gap-event producers over compliance history (DEVELOPMENT_PLAN.md M10)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from kosha.audit import build_report
from kosha.evidence import CoverageKind, SourceCoverage
from kosha.gaps.model import GapKind, GapReasonCode, GapStatus
from kosha.gaps.produce import evidenced_categories, gaps_from_compliance_report
from kosha.git_store import GitStore
from kosha.pipeline import ingest

_ASOF = datetime(2026, 6, 28, tzinfo=UTC)
_AT = datetime(2026, 7, 12, tzinfo=UTC)


def _seed_bundle(tmp_path: Path) -> tuple[Path, GitStore]:
    bundle = tmp_path / "bundle"
    (bundle / "policies").mkdir(parents=True)
    (bundle / "policies" / "returns.md").write_text(
        "---\ntype: policy\ntitle: Returns\n"
        "description: When and how customers may return products.\n---\n"
        "Standard returns are accepted within 30 days of delivery.\n",
        encoding="utf-8",
    )
    store = GitStore.init(bundle)
    store.commit(["policies/returns.md"], "chore: seed")
    return bundle, store


def _policy_update_source(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    (source / "policies").mkdir(parents=True)
    (source / "policies" / "returns.md").write_text(
        "# Returns\n\nStandard returns are accepted within 60 days of delivery.\n",
        encoding="utf-8",
    )
    return source


def _add_legacy_commit(bundle: Path, store: GitStore) -> None:
    (bundle / "policies" / "shipping.md").write_text(
        "---\ntype: policy\ntitle: Shipping\n---\nShips within 3 days.\n", encoding="utf-8"
    )
    store.commit(
        ["policies/shipping.md"],
        "feat(kosha): ingest legacy\n\n- create policies/shipping.md",
    )


def _add_windowed_coverage_commit(tmp_path: Path, bundle: Path, store: GitStore) -> None:
    result = ingest(
        _policy_update_source(tmp_path),
        bundle,
        asof=_ASOF,
        source_authority=10,
        git_store=store,
        branch="ingest/windowed",
        coverage=SourceCoverage(kind=CoverageKind.WINDOWED, scope="last 24h"),
    )
    assert result.committed is True


def test_a_legacy_commit_produces_one_legacy_evidence_gap_event(tmp_path: Path) -> None:
    bundle, store = _seed_bundle(tmp_path)
    _add_legacy_commit(bundle, store)

    report = build_report(bundle)
    events = gaps_from_compliance_report(report, at=_AT)

    legacy_events = [e for e in events if e.kind is GapKind.LEGACY_EVIDENCE]
    assert len(legacy_events) == 1
    event = legacy_events[0]
    assert event.status is GapStatus.OPEN
    assert event.reason_code is GapReasonCode.MISSING_SOURCE_RUN_TRAILER
    assert event.affected_concept_ids == ("policies/shipping.md",)


def test_a_windowed_coverage_change_produces_one_incomplete_coverage_gap_event(
    tmp_path: Path,
) -> None:
    bundle, store = _seed_bundle(tmp_path)
    _add_windowed_coverage_commit(tmp_path, bundle, store)

    report = build_report(bundle)
    events = gaps_from_compliance_report(report, at=_AT)

    coverage_events = [e for e in events if e.kind is GapKind.INCOMPLETE_COVERAGE]
    assert len(coverage_events) == 1
    event = coverage_events[0]
    assert event.status is GapStatus.OPEN
    assert event.reason_code is GapReasonCode.COVERAGE_WINDOWED
    assert event.affected_concept_ids == ("policies/returns.md",)
    assert event.source_run_ids  # the M3 Source-Run trailer is present


def test_a_seed_only_bundle_with_complete_coverage_produces_no_gap_events(
    tmp_path: Path,
) -> None:
    bundle, store = _seed_bundle(tmp_path)
    result = ingest(
        _policy_update_source(tmp_path),
        bundle,
        asof=_ASOF,
        source_authority=10,
        git_store=store,
        branch="ingest/complete",
    )
    assert result.committed is True

    report = build_report(bundle)
    events = gaps_from_compliance_report(report, at=_AT)

    assert events == ()


def test_a_history_with_both_signals_evidences_at_least_two_categories(tmp_path: Path) -> None:
    bundle, store = _seed_bundle(tmp_path)
    _add_legacy_commit(bundle, store)
    _add_windowed_coverage_commit(tmp_path, bundle, store)

    report = build_report(bundle)
    events = gaps_from_compliance_report(report, at=_AT)
    categories = evidenced_categories(events)

    assert categories == {GapKind.LEGACY_EVIDENCE, GapKind.INCOMPLETE_COVERAGE}


def test_re_running_the_producer_against_unchanged_history_reproduces_the_same_gap_ids(
    tmp_path: Path,
) -> None:
    bundle, store = _seed_bundle(tmp_path)
    _add_legacy_commit(bundle, store)

    report = build_report(bundle)
    first = gaps_from_compliance_report(report, at=_AT)
    second = gaps_from_compliance_report(report, at=datetime(2026, 8, 1, tzinfo=UTC))

    assert {e.gap_id for e in first} == {e.gap_id for e in second}


def test_no_producer_takes_a_model_generated_question_only_a_compliance_report() -> None:
    # The only input any producer in kosha.gaps.produce accepts is a
    # deterministic ComplianceReport plus a timestamp -- there is no
    # free-text/model-generated parameter to pass a speculative gap through.
    import inspect
    import typing

    signature = inspect.signature(gaps_from_compliance_report)
    assert set(signature.parameters) == {"report", "at"}
    hints = typing.get_type_hints(gaps_from_compliance_report)
    assert hints["report"].__name__ == "ComplianceReport"
