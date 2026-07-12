"""Source coverage and run-completeness contracts (DEVELOPMENT_PLAN.md M5).

Coverage answers what portion of a source a run observed; authority
(`Source.authority_rank`) answers which source wins when assertions conflict.
These tests verify the two stay separate and that the model never invents
completeness a caller did not establish.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from kosha.evidence.model import (
    CoverageKind,
    EvidenceDocument,
    RunStatus,
    SourceCoverage,
    SourceRun,
    source_run_from_json,
    source_run_to_json,
)

_ASOF = datetime(2026, 7, 12, tzinfo=UTC)


def _run(*, coverage: SourceCoverage | None = None) -> SourceRun:
    return SourceRun(
        run_id="run-1",
        bundle_identity="b" * 64,
        source_instance_id="instance-1",
        adapter="markdown",
        adapter_version="1",
        started_at=_ASOF,
        completed_at=_ASOF,
        status=RunStatus.ACCEPTED,
        **({"coverage": coverage} if coverage is not None else {}),
    )


# --- honest defaults ----------------------------------------------------------


def test_coverage_defaults_to_unknown_not_complete() -> None:
    assert SourceCoverage().kind is CoverageKind.UNKNOWN


def test_a_source_run_with_no_explicit_coverage_defaults_to_unknown() -> None:
    run = _run()
    assert run.coverage.kind is CoverageKind.UNKNOWN


def test_a_legacy_manifest_with_no_coverage_key_loads_as_unknown_not_complete() -> None:
    # A pre-M5 manifest on disk has no "coverage" key at all; loading it must
    # never be silently upgraded to "complete".
    raw = source_run_to_json(_run())
    del raw["coverage"]
    loaded = source_run_from_json(raw)
    assert loaded.coverage.kind is CoverageKind.UNKNOWN


# --- no false completeness -----------------------------------------------------


def test_a_truncated_run_cannot_declare_complete_coverage() -> None:
    with pytest.raises(ValidationError, match="truncated"):
        SourceCoverage(kind=CoverageKind.COMPLETE, truncated=True)


def test_a_permission_limited_run_cannot_declare_complete_coverage() -> None:
    with pytest.raises(ValidationError, match="permission-limited"):
        SourceCoverage(kind=CoverageKind.COMPLETE, permission_limited=True)


def test_a_truncated_best_effort_run_is_valid() -> None:
    coverage = SourceCoverage(kind=CoverageKind.BEST_EFFORT, truncated=True)
    assert coverage.truncated is True


# --- window sanity --------------------------------------------------------------


def test_a_requested_window_end_before_its_start_is_rejected() -> None:
    with pytest.raises(ValidationError, match="requested window"):
        SourceCoverage(
            kind=CoverageKind.WINDOWED,
            requested_window_start=datetime(2026, 7, 12, tzinfo=UTC),
            requested_window_end=datetime(2026, 7, 11, tzinfo=UTC),
        )


def test_an_observed_window_end_before_its_start_is_rejected() -> None:
    with pytest.raises(ValidationError, match="observed window"):
        SourceCoverage(
            kind=CoverageKind.WINDOWED,
            observed_window_start=datetime(2026, 7, 12, tzinfo=UTC),
            observed_window_end=datetime(2026, 7, 11, tzinfo=UTC),
        )


def test_an_equal_window_start_and_end_is_valid() -> None:
    moment = datetime(2026, 7, 12, tzinfo=UTC)
    coverage = SourceCoverage(
        kind=CoverageKind.WINDOWED,
        requested_window_start=moment,
        requested_window_end=moment,
    )
    assert coverage.requested_window_end == moment


# --- every classification round-trips through the manifest ---------------------


@pytest.mark.parametrize("kind", list(CoverageKind))
def test_every_coverage_kind_round_trips_through_json(kind: CoverageKind) -> None:
    coverage = SourceCoverage(kind=kind, scope="test scope")
    run = _run(coverage=coverage)
    loaded = source_run_from_json(source_run_to_json(run))
    assert loaded.coverage.kind is kind
    assert loaded.coverage.scope == "test scope"


def test_a_windowed_run_with_explicit_bounds_round_trips() -> None:
    coverage = SourceCoverage(
        kind=CoverageKind.WINDOWED,
        scope="last 24h of the changelog feed",
        requested_window_start=datetime(2026, 7, 11, tzinfo=UTC),
        requested_window_end=datetime(2026, 7, 12, tzinfo=UTC),
        observed_window_start=datetime(2026, 7, 11, tzinfo=UTC),
        observed_window_end=datetime(2026, 7, 12, tzinfo=UTC),
    )
    loaded = source_run_from_json(source_run_to_json(_run(coverage=coverage)))
    assert loaded.coverage.requested_window_start == coverage.requested_window_start
    assert loaded.coverage.observed_window_end == coverage.observed_window_end


def test_a_cursor_incremental_run_carries_before_and_after_cursors() -> None:
    coverage = SourceCoverage(
        kind=CoverageKind.CURSOR_INCREMENTAL,
        cursor_before="commit-abc",
        cursor_after="commit-def",
    )
    loaded = source_run_from_json(source_run_to_json(_run(coverage=coverage)))
    assert loaded.coverage.cursor_before == "commit-abc"
    assert loaded.coverage.cursor_after == "commit-def"


def test_a_sampled_run_carries_configured_and_observed_item_counts() -> None:
    coverage = SourceCoverage(
        kind=CoverageKind.SAMPLED,
        configured_item_limit=100,
        observed_item_count=25,
    )
    loaded = source_run_from_json(source_run_to_json(_run(coverage=coverage)))
    assert loaded.coverage.configured_item_limit == 100
    assert loaded.coverage.observed_item_count == 25


def test_a_permission_limited_run_carries_a_non_secret_warning() -> None:
    coverage = SourceCoverage(
        kind=CoverageKind.BEST_EFFORT,
        permission_limited=True,
        warnings=("3 of 10 pages were not readable by the configured credentials",),
    )
    loaded = source_run_from_json(source_run_to_json(_run(coverage=coverage)))
    assert loaded.coverage.permission_limited is True
    assert "not readable" in loaded.coverage.warnings[0]


# --- warnings are enforced, not just documented convention ----------------------


def test_a_warning_matching_a_known_credential_shape_is_rejected() -> None:
    with pytest.raises(ValidationError, match="secret detector"):
        SourceCoverage(
            kind=CoverageKind.BEST_EFFORT,
            truncated=True,
            warnings=("deploy key: AKIAABCDEFGHIJKLMNOP for the release pipeline",),
        )


def test_a_warning_matching_a_generic_credential_assignment_is_rejected() -> None:
    with pytest.raises(ValidationError, match="secret detector"):
        SourceCoverage(
            kind=CoverageKind.UNKNOWN,
            warnings=("api_key: 'sk-abcdefghijklmnopqrstuvwx'",),
        )


def test_an_oversized_warning_is_rejected_even_without_a_secret_shape() -> None:
    # A length cap keeps a "warning" from becoming a vehicle for pasting a
    # source excerpt that merely does not match a known credential pattern.
    with pytest.raises(ValidationError, match="500 chars"):
        SourceCoverage(kind=CoverageKind.UNKNOWN, warnings=("x" * 501,))


def test_a_benign_warning_at_the_length_boundary_is_accepted() -> None:
    coverage = SourceCoverage(kind=CoverageKind.UNKNOWN, warnings=("x" * 500,))
    assert coverage.warnings == ("x" * 500,)


# --- coverage is a separate field from authority --------------------------------


def test_source_coverage_has_no_authority_field() -> None:
    # Authority lives on Source.authority_rank, never here -- overloading it
    # with completeness would let a partial retrieval outrank a source it
    # never fully saw.
    assert not hasattr(SourceCoverage(), "authority_rank")


def test_evidence_document_carries_no_coverage_field() -> None:
    # Coverage is a run-level classification, not a per-document one.
    document = EvidenceDocument(
        sha256="a" * 64,
        source_id="s",
        location="s",
        media_type="text/plain",
        normalized_text_bytes=1,
        normalization_version="1",
    )
    assert not hasattr(document, "coverage")
