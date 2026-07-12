"""Connector run orchestration: transactional cursor advancement (M6).

Mirrors ``tests/ingest/test_watch.py``'s discipline: the pipeline's own
approval gate runs for real; only the network/filesystem boundary a
connector's ingest function crosses is faked where a test needs to force a
FAILED outcome.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from kosha.approve import Decision
from kosha.connectors.config import URL_CONNECTOR
from kosha.connectors.model import SourceInstance, SourceRunOutcome
from kosha.connectors.run import run_source_instance
from kosha.connectors.state import ConnectorStateStore
from kosha.git_store import GitStore
from kosha.ingest.url import UrlIngestError

_ASOF = datetime(2026, 6, 28, tzinfo=UTC)


def _seed_bundle(tmp_path: Path) -> Path:
    bundle = tmp_path / "bundle"
    (bundle / "policies").mkdir(parents=True)
    (bundle / "policies" / "returns.md").write_text(
        "---\ntype: policy\ntitle: Returns\n"
        "description: When and how customers may return products.\n---\n"
        "Standard returns are accepted within 30 days of delivery.\n",
        encoding="utf-8",
    )
    GitStore.init(bundle).commit(["policies/returns.md"], "chore: seed")
    return bundle


def _seed_source(tmp_path: Path, *, name: str = "source", body: str = "shipping.md") -> Path:
    source = tmp_path / name
    source.mkdir()
    (source / body).write_text(
        "---\ntype: policy\ntitle: Shipping\ndescription: How shipping works.\n---\n"
        "Orders ship within 2 business days.\n",
        encoding="utf-8",
    )
    return source


def _instance(instance_id: str, source: Path) -> SourceInstance:
    return SourceInstance(
        instance_id=instance_id, connector_id="folder", config={"path": str(source)}
    )


# --- successful cursor advancement -------------------------------------


def test_a_successful_committed_run_advances_state_and_records_success(
    tmp_path: Path,
) -> None:
    bundle = _seed_bundle(tmp_path)
    source = _seed_source(tmp_path)
    store = ConnectorStateStore(tmp_path / "connectors")
    instance = _instance("policies", source)

    report = run_source_instance(
        instance, bundle_root=bundle, state_store=store, assume_yes=True, asof=_ASOF
    )

    assert report.outcome is SourceRunOutcome.SUCCESS
    assert report.ingest_result is not None
    assert report.ingest_result.committed is True
    assert report.state.last_success_run_id == report.run_id
    assert report.state.last_success_at == _ASOF
    assert [r.status for r in report.state.recent_runs] == [SourceRunOutcome.SUCCESS]
    # persisted, not just returned
    reloaded = store.load("policies")
    assert reloaded == report.state


# --- failed run preserves prior cursor ----------------------------------


def test_a_raised_connector_exception_is_recorded_failed_and_preserves_the_cursor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _seed_bundle(tmp_path)
    source = _seed_source(tmp_path)
    store = ConnectorStateStore(tmp_path / "connectors")
    instance = _instance("policies", source)

    # First run succeeds and establishes a prior state to protect.
    first = run_source_instance(
        instance, bundle_root=bundle, state_store=store, assume_yes=True, asof=_ASOF
    )
    assert first.outcome is SourceRunOutcome.SUCCESS
    prior_state = store.load("policies")
    assert prior_state is not None

    def _boom(*_args: object, **_kwargs: object) -> object:
        raise UrlIngestError("simulated adapter failure")

    # The connector's ingest function drives `ingest_folder()` internally
    # (via `kosha.pipeline.run.ingest`); faking that one true I/O boundary
    # exercises the real exception-handling path in `run_source_instance`.
    monkeypatch.setattr("kosha.pipeline.run.ingest_folder", _boom)

    second = run_source_instance(
        instance,
        bundle_root=bundle,
        state_store=store,
        assume_yes=True,
        asof=_ASOF,
    )

    assert second.outcome is SourceRunOutcome.FAILED
    assert second.ingest_result is None
    assert "simulated adapter failure" in second.message

    reloaded = store.load("policies")
    assert reloaded is not None
    assert reloaded.cursor == prior_state.cursor
    assert reloaded.last_success_run_id == prior_state.last_success_run_id
    assert reloaded.last_success_at == prior_state.last_success_at
    assert [r.status for r in reloaded.recent_runs] == [
        SourceRunOutcome.SUCCESS,
        SourceRunOutcome.FAILED,
    ]


def test_a_failure_message_that_looks_credential_shaped_is_withheld(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _seed_bundle(tmp_path)
    source = _seed_source(tmp_path)
    store = ConnectorStateStore(tmp_path / "connectors")
    instance = _instance("policies", source)

    def _boom(*_args: object, **_kwargs: object) -> object:
        raise UrlIngestError("token: 'sk-abcdefghijklmnopqrstuvwx'")

    monkeypatch.setattr("kosha.pipeline.run.ingest_folder", _boom)

    report = run_source_instance(
        instance, bundle_root=bundle, state_store=store, assume_yes=True, asof=_ASOF
    )
    assert report.outcome is SourceRunOutcome.FAILED
    assert "sk-abcdefghijklmnopqrstuvwx" not in report.message
    assert "withheld" in report.message


# --- rejected run preserves prior cursor --------------------------------


def test_a_declined_approval_is_recorded_rejected_and_preserves_the_cursor(
    tmp_path: Path,
) -> None:
    bundle = _seed_bundle(tmp_path)
    source = _seed_source(tmp_path)
    store = ConnectorStateStore(tmp_path / "connectors")
    instance = _instance("policies", source)

    first = run_source_instance(
        instance, bundle_root=bundle, state_store=store, assume_yes=True, asof=_ASOF
    )
    assert first.outcome is SourceRunOutcome.SUCCESS

    # A secret-bearing document forces the BLOCK lane (requires_approval);
    # declining it (assume_yes=False, no reader) must not advance the cursor.
    secret_source = tmp_path / "secret-source"
    secret_source.mkdir()
    (secret_source / "leaked.md").write_text(
        "---\ntype: policy\ntitle: Leaked\ndescription: x.\n---\n"
        "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\n",
        encoding="utf-8",
    )
    secret_instance = _instance("policies", secret_source)
    second = run_source_instance(
        secret_instance,
        bundle_root=bundle,
        state_store=store,
        assume_yes=False,
        reader=None,
        asof=_ASOF,
    )

    assert second.outcome is SourceRunOutcome.REJECTED
    assert second.ingest_result is not None
    assert second.ingest_result.committed is False

    reloaded = store.load("policies")
    assert reloaded is not None
    assert reloaded.last_success_run_id == first.run_id
    assert [r.status for r in reloaded.recent_runs] == [
        SourceRunOutcome.SUCCESS,
        SourceRunOutcome.REJECTED,
    ]


def test_a_dry_run_never_commits_or_advances_the_cursor(tmp_path: Path) -> None:
    bundle = _seed_bundle(tmp_path)
    source = _seed_source(tmp_path)
    store = ConnectorStateStore(tmp_path / "connectors")
    instance = _instance("policies", source)

    report = run_source_instance(
        instance,
        bundle_root=bundle,
        state_store=store,
        assume_yes=True,
        dry_run=True,
        asof=_ASOF,
    )

    assert report.outcome is SourceRunOutcome.REJECTED
    assert report.message.startswith("dry run")
    assert report.state.cursor is None
    assert report.state.last_success_run_id is None


# --- two instances of one connector stay isolated -----------------------


def test_two_instances_of_the_same_connector_have_isolated_state(tmp_path: Path) -> None:
    bundle = _seed_bundle(tmp_path)
    store = ConnectorStateStore(tmp_path / "connectors")
    source_a = _seed_source(tmp_path, name="source-a", body="a.md")
    source_b = _seed_source(tmp_path, name="source-b", body="b.md")
    instance_a = _instance("instance-a", source_a)
    instance_b = _instance("instance-b", source_b)

    report_a = run_source_instance(
        instance_a, bundle_root=bundle, state_store=store, assume_yes=True, asof=_ASOF
    )
    report_b = run_source_instance(
        instance_b, bundle_root=bundle, state_store=store, assume_yes=True, asof=_ASOF
    )

    assert report_a.outcome is SourceRunOutcome.SUCCESS
    assert report_b.outcome is SourceRunOutcome.SUCCESS
    assert report_a.run_id != report_b.run_id
    assert store.load("instance-a").last_success_run_id == report_a.run_id  # type: ignore[union-attr]
    assert store.load("instance-b").last_success_run_id == report_b.run_id  # type: ignore[union-attr]
    assert (
        store.load("instance-a").last_success_run_id  # type: ignore[union-attr]
        != store.load("instance-b").last_success_run_id  # type: ignore[union-attr]
    )


# --- malformed on-disk state fails loud, never silently resets ----------


def test_a_corrupt_prior_state_fails_loud_instead_of_starting_fresh(tmp_path: Path) -> None:
    bundle = _seed_bundle(tmp_path)
    source = _seed_source(tmp_path)
    store_root = tmp_path / "connectors"
    (store_root / "policies").mkdir(parents=True)
    (store_root / "policies" / "state.json").write_text("{not json", encoding="utf-8")
    store = ConnectorStateStore(store_root)
    instance = _instance("policies", source)

    with pytest.raises(Exception, match="malformed connector state"):
        run_source_instance(
            instance, bundle_root=bundle, state_store=store, assume_yes=True, asof=_ASOF
        )


# --- source run uses the normal approval path ----------------------------


def test_source_run_routes_through_the_normal_approval_path(tmp_path: Path) -> None:
    bundle = _seed_bundle(tmp_path)
    store = ConnectorStateStore(tmp_path / "connectors")

    def _secret_source(name: str) -> SourceInstance:
        source = tmp_path / name
        source.mkdir()
        (source / "leaked.md").write_text(
            "---\ntype: policy\ntitle: Leaked\ndescription: x.\n---\n"
            "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\n",
            encoding="utf-8",
        )
        return _instance("policies", source)

    # No reader, assume_yes False -> the BLOCK-lane secret is declined by
    # default, exactly like `kosha ingest` with neither --yes nor a tty.
    rejected = run_source_instance(
        _secret_source("secret-a"),
        bundle_root=bundle,
        state_store=store,
        assume_yes=False,
        reader=None,
        asof=_ASOF,
    )
    assert rejected.ingest_result is not None
    assert rejected.ingest_result.routing.requires_approval is True
    assert rejected.ingest_result.decision is Decision.REJECT
    assert rejected.outcome is SourceRunOutcome.REJECTED

    # An explicit reader supplying "yes" approves the same shaped request.
    approved = run_source_instance(
        _secret_source("secret-b"),
        bundle_root=bundle,
        state_store=store,
        assume_yes=False,
        reader=lambda _prompt: "yes",
        asof=_ASOF,
    )
    assert approved.ingest_result is not None
    assert approved.ingest_result.decision is Decision.APPROVE
    assert approved.outcome is SourceRunOutcome.SUCCESS


# --- URL connector wiring (existing adapter, not a new implementation) ---


def test_the_url_connector_reports_complete_coverage_scoped_to_the_response_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from kosha.model import RawDoc, Source, SourceKind

    bundle = _seed_bundle(tmp_path)
    store = ConnectorStateStore(tmp_path / "connectors")
    instance = SourceInstance(
        instance_id="web-page", connector_id="url", config={"url": "https://trusted.example/page"}
    )

    raw = RawDoc(
        source=Source(
            source_id="page.md",
            kind=SourceKind.URL,
            location="https://trusted.example/page",
        ),
        text="# Warranty\n\nProducts are covered for one year from purchase.\n",
    )
    monkeypatch.setattr("kosha.connectors.config.fetch_url", lambda url, **kwargs: raw)

    report = run_source_instance(
        instance, bundle_root=bundle, state_store=store, assume_yes=True, asof=_ASOF
    )
    assert report.outcome is SourceRunOutcome.SUCCESS
    assert report.ingest_result is not None
    assert report.ingest_result.evidence_run is not None
    coverage = report.ingest_result.evidence_run.run.coverage
    assert coverage.kind.value == "complete"
    assert "https://trusted.example/page" in (coverage.scope or "")
    assert URL_CONNECTOR.connector_id == "url"
