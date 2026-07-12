"""The shared evidence boundary: scan, digest, and bind identity before extraction."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from kosha.evidence import (
    CoverageKind,
    EvidenceStore,
    RunStatus,
    SourceCoverage,
    hash_evidence_text,
)
from kosha.ingest.guardrails import EvidenceRun, bind_evidence, persist_evidence_run
from kosha.model import RawDoc, Source, SourceKind

_ASOF = datetime(2026, 6, 28, tzinfo=UTC)


def _raw(text: str, *, source_id: str = "a.md") -> RawDoc:
    return RawDoc(
        source=Source(source_id=source_id, kind=SourceKind.MARKDOWN, location=source_id),
        text=text,
    )


def _bind(docs: list[RawDoc]) -> tuple[list[RawDoc], EvidenceRun | None]:
    return bind_evidence(
        docs,
        run_id="run-1",
        bundle_identity="b" * 64,
        source_instance_id="src",
        started_at=_ASOF,
        completed_at=_ASOF,
    )


# --- clean documents ---------------------------------------------------------


def test_a_clean_document_is_stamped_with_run_id_and_content_digest() -> None:
    docs, run = _bind([_raw("Standard returns are accepted within 30 days.")])
    assert run is not None
    bound = docs[0]
    assert bound.source_run_id == "run-1"
    assert bound.evidence_sha256 == hash_evidence_text(bound.text)


def test_binding_never_writes_to_disk() -> None:
    # A pure hash: no store is threaded through bind_evidence at all.
    docs, run = _bind([_raw("no filesystem access happens here")])
    assert run is not None
    assert run.texts[docs[0].evidence_sha256] == docs[0].text


def test_evidence_run_status_is_accepted_when_any_document_is_clean() -> None:
    _, run = _bind([_raw("clean text")])
    assert run is not None
    assert run.run.status is RunStatus.ACCEPTED
    assert len(run.run.evidence) == 1


def test_identical_text_across_two_runs_yields_the_same_digest() -> None:
    docs_a, run_a = _bind([_raw("same content", source_id="a.md")])
    docs_b, run_b = bind_evidence(
        [_raw("same content", source_id="a.md")],
        run_id="run-2",
        bundle_identity="b" * 64,
        source_instance_id="src",
        started_at=_ASOF,
        completed_at=_ASOF,
    )
    assert run_a is not None and run_b is not None
    assert docs_a[0].evidence_sha256 == docs_b[0].evidence_sha256
    # Distinct runs still get distinct run identity over the same content.
    assert run_a.run.run_id != run_b.run.run_id


def test_a_changed_document_produces_a_different_digest() -> None:
    docs_a, _ = _bind([_raw("version one", source_id="a.md")])
    docs_b, _ = _bind([_raw("version two", source_id="a.md")])
    assert docs_a[0].evidence_sha256 != docs_b[0].evidence_sha256


# --- secret-tainted documents -------------------------------------------------


_SECRET_TEXT = "deploy key: AKIAABCDEFGHIJKLMNOP for the release pipeline."


def test_a_secret_bearing_document_gets_no_evidence_identity() -> None:
    docs, run = _bind([_raw(_SECRET_TEXT)])
    assert run is not None
    bound = docs[0]
    assert bound.source_run_id is None
    assert bound.evidence_sha256 is None
    assert run.run.evidence == ()
    assert "aws-access-key-id" in run.run.detector_names


def test_a_secret_bearing_document_still_reaches_extraction_unstamped() -> None:
    # The early scan excludes a tainted document from evidence, not from the
    # pipeline: it must still flow through so the existing final-plan scan
    # remains a working second line of defense (DEVELOPMENT_PLAN.md M3).
    docs, _ = _bind([_raw(_SECRET_TEXT)])
    assert len(docs) == 1
    assert docs[0].text == _SECRET_TEXT


def test_a_mixed_batch_keeps_the_clean_document_evidenced_and_the_tainted_one_bare() -> None:
    docs, run = _bind([_raw("clean.", source_id="a.md"), _raw(_SECRET_TEXT, source_id="b.md")])
    assert run is not None
    clean, tainted = docs
    assert clean.evidence_sha256 is not None
    assert tainted.evidence_sha256 is None
    assert run.run.status is RunStatus.ACCEPTED
    assert len(run.run.evidence) == 1


def test_an_all_secret_batch_is_a_rejected_run_with_no_evidence() -> None:
    _, run = _bind([_raw(_SECRET_TEXT)])
    assert run is not None
    assert run.run.status is RunStatus.REJECTED
    assert run.run.evidence == ()


# --- empty input ---------------------------------------------------------------


def test_no_documents_produces_no_evidence_run() -> None:
    docs, run = _bind([])
    assert docs == []
    assert run is None


# --- durable persistence --------------------------------------------------------


def test_persist_evidence_run_writes_objects_before_the_manifest(tmp_path: Path) -> None:
    docs, run = _bind([_raw("durable text")])
    assert run is not None
    store = EvidenceStore(tmp_path / "vault")
    persist_evidence_run(store, run)

    loaded = store.read_run("run-1")
    assert loaded.status is RunStatus.ACCEPTED
    assert loaded.evidence[0].sha256 == docs[0].evidence_sha256
    assert store.read_object(docs[0].evidence_sha256) == docs[0].text


def test_persist_evidence_run_is_a_noop_for_a_rejected_run(tmp_path: Path) -> None:
    _, run = _bind([_raw(_SECRET_TEXT)])
    assert run is not None
    store = EvidenceStore(tmp_path / "vault")
    persist_evidence_run(store, run)

    assert not store.root.exists()


# --- coverage: honest by default, explicit when supplied ------------------------


def test_bind_evidence_without_an_explicit_coverage_defaults_to_unknown() -> None:
    # bind_evidence never infers "complete" on its own -- only the caller
    # knows whether a traversal, response, or bounded fetch was exhaustive.
    _, run = _bind([_raw("clean text")])
    assert run is not None
    assert run.run.coverage.kind is CoverageKind.UNKNOWN


def test_bind_evidence_threads_an_explicit_coverage_onto_the_run() -> None:
    coverage = SourceCoverage(kind=CoverageKind.COMPLETE, scope="one fetched response body")
    _docs, run = bind_evidence(
        [_raw("clean text")],
        run_id="run-1",
        bundle_identity="b" * 64,
        source_instance_id="src",
        started_at=_ASOF,
        completed_at=_ASOF,
        coverage=coverage,
    )
    assert run is not None
    assert run.run.coverage == coverage


def test_bind_evidence_threads_a_windowed_coverage_with_explicit_bounds() -> None:
    coverage = SourceCoverage(
        kind=CoverageKind.WINDOWED,
        scope="changelog feed, last 24h",
        requested_window_start=datetime(2026, 6, 27, tzinfo=UTC),
        requested_window_end=_ASOF,
        observed_window_start=datetime(2026, 6, 27, tzinfo=UTC),
        observed_window_end=_ASOF,
    )
    _, run = bind_evidence(
        [_raw("clean text")],
        run_id="run-1",
        bundle_identity="b" * 64,
        source_instance_id="src",
        started_at=_ASOF,
        completed_at=_ASOF,
        coverage=coverage,
    )
    assert run is not None
    assert run.run.coverage.kind is CoverageKind.WINDOWED
    assert run.run.coverage.observed_window_end == _ASOF


def test_bind_evidence_threads_a_truncated_best_effort_coverage_with_a_warning() -> None:
    coverage = SourceCoverage(
        kind=CoverageKind.BEST_EFFORT,
        truncated=True,
        warnings=("stopped after the configured byte cap; more content may remain",),
    )
    _, run = bind_evidence(
        [_raw("clean text")],
        run_id="run-1",
        bundle_identity="b" * 64,
        source_instance_id="src",
        started_at=_ASOF,
        completed_at=_ASOF,
        coverage=coverage,
    )
    assert run is not None
    assert run.run.coverage.truncated is True
    assert "AKIA" not in run.run.coverage.warnings[0]
    assert "byte cap" in run.run.coverage.warnings[0]


def test_bind_evidence_threads_a_permission_limited_cursor_incremental_coverage() -> None:
    coverage = SourceCoverage(
        kind=CoverageKind.CURSOR_INCREMENTAL,
        permission_limited=True,
        cursor_before="cursor-0",
        cursor_after="cursor-1",
        warnings=("2 of 8 items were skipped: insufficient read permission",),
    )
    _, run = bind_evidence(
        [_raw("clean text")],
        run_id="run-1",
        bundle_identity="b" * 64,
        source_instance_id="src",
        started_at=_ASOF,
        completed_at=_ASOF,
        coverage=coverage,
    )
    assert run is not None
    assert run.run.coverage.permission_limited is True
    assert run.run.coverage.cursor_after == "cursor-1"


def test_a_rejected_run_still_carries_whatever_coverage_the_caller_supplied() -> None:
    # Coverage describes the source-run attempt, independent of whether any
    # document survived the secret scan.
    coverage = SourceCoverage(kind=CoverageKind.SAMPLED, observed_item_count=0)
    _, run = bind_evidence(
        [_raw(_SECRET_TEXT)],
        run_id="run-1",
        bundle_identity="b" * 64,
        source_instance_id="src",
        started_at=_ASOF,
        completed_at=_ASOF,
        coverage=coverage,
    )
    assert run is not None
    assert run.run.status is RunStatus.REJECTED
    assert run.run.coverage.kind is CoverageKind.SAMPLED


def test_persist_evidence_run_preserves_coverage_through_the_stored_manifest(
    tmp_path: Path,
) -> None:
    coverage = SourceCoverage(kind=CoverageKind.COMPLETE, scope="one local file snapshot")
    _docs, run = bind_evidence(
        [_raw("durable text")],
        run_id="run-1",
        bundle_identity="b" * 64,
        source_instance_id="src",
        started_at=_ASOF,
        completed_at=_ASOF,
        coverage=coverage,
    )
    assert run is not None
    store = EvidenceStore(tmp_path / "vault")
    persist_evidence_run(store, run)

    loaded = store.read_run("run-1")
    assert loaded.coverage == coverage
