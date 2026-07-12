"""Scheduled/watch ingest: source policy guards never bypass the approval gate (M9 PR-3).

``ScheduledIngest.run_once`` is the deterministic unit under test (no real
interval scheduling here, which would need wall-clock waits). The network
fetch is the one true external boundary, so it is the only thing faked:
scheme/SSRF checks and the pipeline's own approval gate run for real.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from kosha.approve import Decision
from kosha.evidence import CoverageKind
from kosha.git_store import GitStore
from kosha.ingest.url import UrlIngestError
from kosha.ingest.watch import ScheduledIngest, SourcePolicy
from kosha.model import RawDoc, Source, SourceKind
from kosha.pipeline import ingest as pipeline_ingest
from kosha.providers import ExtractiveGenerationProvider, LexicalEmbeddingProvider

_ASOF = datetime(2026, 6, 28, tzinfo=UTC)


class _UnexpectedNetworkCall(AssertionError):
    """Raised by a test spy when a guard should have stopped execution first."""


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


def _raw_doc(text: str) -> RawDoc:
    return RawDoc(
        source=Source(
            source_id="watch-fetch.md", kind=SourceKind.URL, location="https://trusted.example/page"
        ),
        text=text,
    )


def _reject_if_called(*_args: object, **_kwargs: object) -> object:
    raise _UnexpectedNetworkCall("this must not run once a source-policy guard rejects the source")


# --- source policy: explicit host allowlist ---------------------------------


def test_a_host_outside_the_allowlist_is_rejected_before_any_fetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _seed_bundle(tmp_path)
    policy = SourcePolicy(max_bytes=1024, allowed_hosts=frozenset({"trusted.example"}))
    monkeypatch.setattr("kosha.ingest.watch.fetch_url", _reject_if_called)
    monkeypatch.setattr("kosha.ingest.watch.ingest", _reject_if_called)

    scheduled = ScheduledIngest(
        "https://not-allowed.example/page", bundle, policy, assume_yes=True, now=lambda: _ASOF
    )

    with pytest.raises(UrlIngestError, match="not in the scheduled source allowlist"):
        scheduled.run_once()


def test_an_empty_allowlist_permits_any_host_through_to_the_fetch_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An empty allowlist means "no policy-level host restriction" -- the
    # request must still reach (and be judged by) the real fetch_url guard,
    # proving the allowlist and the SSRF guard are independent layers.
    bundle = _seed_bundle(tmp_path)
    policy = SourcePolicy(max_bytes=1024, allowed_hosts=frozenset())
    monkeypatch.setattr("kosha.ingest.watch.ingest", _reject_if_called)

    scheduled = ScheduledIngest(
        "http://169.254.169.254/latest/meta-data/",
        bundle,
        policy,
        assume_yes=True,
        now=lambda: _ASOF,
    )

    with pytest.raises(UrlIngestError, match="non-public address"):
        scheduled.run_once()


def test_a_non_http_scheme_is_never_treated_as_a_fetchable_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # ScheduledIngest only recognizes http(s) as a URL; any other scheme
    # falls through to local-path handling and fails closed instead of
    # silently fetching over an unvetted protocol.
    bundle = _seed_bundle(tmp_path)
    policy = SourcePolicy(max_bytes=1024, allowed_hosts=frozenset({"trusted.example"}))
    monkeypatch.setattr("kosha.ingest.watch.fetch_url", _reject_if_called)

    scheduled = ScheduledIngest(
        "ftp://trusted.example/page", bundle, policy, assume_yes=True, now=lambda: _ASOF
    )

    with pytest.raises(NotADirectoryError):
        scheduled.run_once()


# --- source policy: response-size cap ---------------------------------------


def test_policy_max_bytes_is_threaded_into_the_fetch_and_a_cap_violation_blocks_ingest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _seed_bundle(tmp_path)
    policy = SourcePolicy(max_bytes=2048, allowed_hosts=frozenset({"trusted.example"}))
    seen_kwargs: dict[str, object] = {}

    def _oversized_fetch(url: str, **kwargs: object) -> RawDoc:
        seen_kwargs.update(kwargs)
        raise UrlIngestError(f"response for {url} exceeded max_bytes")

    monkeypatch.setattr("kosha.ingest.watch.fetch_url", _oversized_fetch)
    monkeypatch.setattr("kosha.ingest.watch.ingest", _reject_if_called)

    scheduled = ScheduledIngest(
        "https://trusted.example/page", bundle, policy, assume_yes=True, now=lambda: _ASOF
    )

    with pytest.raises(UrlIngestError, match="exceeded max_bytes"):
        scheduled.run_once()
    assert seen_kwargs.get("max_bytes") == 2048


# --- no bypass of the existing approval gate --------------------------------


def test_a_secret_bearing_fetch_is_blocked_by_default_and_only_proceeds_with_explicit_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _seed_bundle(tmp_path)
    policy = SourcePolicy(max_bytes=1_000_000, allowed_hosts=frozenset({"trusted.example"}))
    secret_doc = _raw_doc(
        "# Returns\n\nStandard returns are accepted within 60 days of delivery. "
        "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\n"
    )
    monkeypatch.setattr(
        "kosha.ingest.watch.fetch_url", lambda url, **kwargs: secret_doc
    )

    rejected = ScheduledIngest(
        "https://trusted.example/page",
        bundle,
        policy,
        dry_run=False,
        assume_yes=False,
        now=lambda: _ASOF,
    )
    result = rejected.run_once()
    assert result.routing.requires_approval is True
    assert result.decision is Decision.REJECT
    assert result.committed is False

    approved = ScheduledIngest(
        "https://trusted.example/page",
        bundle,
        policy,
        dry_run=False,
        assume_yes=True,
        now=lambda: _ASOF,
    )
    result2 = approved.run_once()
    assert result2.decision is Decision.APPROVE
    assert result2.committed is True


# --- fetched URL provenance reaches the committed concept -------------------


def test_a_fetched_urls_provenance_is_preserved_through_to_the_committed_citation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The RawDoc ScheduledIngest builds from fetch_url must reach ingest()
    # intact via raw_docs=[...] rather than get downgraded to a generic
    # filesystem source -- so the committed concept cites the fetched URL.
    bundle = _seed_bundle(tmp_path)
    policy = SourcePolicy(max_bytes=1_000_000, allowed_hosts=frozenset({"trusted.example"}))
    fetched = _raw_doc(
        "# Shipping\n\nExpedited orders ship within one business day of confirmation.\n"
    )
    monkeypatch.setattr("kosha.ingest.watch.fetch_url", lambda url, **kwargs: fetched)

    scheduled = ScheduledIngest(
        "https://trusted.example/page",
        bundle,
        policy,
        dry_run=False,
        assume_yes=True,
        now=lambda: _ASOF,
    )
    result = scheduled.run_once()

    assert result.committed is True
    created = next(change for change in result.plan.changes if change.concept_id is not None)
    assert "https://trusted.example/page" in created.content


# --- no persistent temp file for the scheduled URL path ---------------------


def test_the_scheduled_url_path_never_writes_a_persistent_temp_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A prior draft wrote the fetched HTML to a temp directory so
    # ingest_folder could read it back; raw_docs=[...] removed that
    # indirection. Fail loud if the scheduled URL path ever touches tempfile.
    bundle = _seed_bundle(tmp_path)
    policy = SourcePolicy(max_bytes=1_000_000, allowed_hosts=frozenset({"trusted.example"}))
    fetched = _raw_doc("# Shipping\n\nExpedited orders ship within one business day.\n")
    monkeypatch.setattr("kosha.ingest.watch.fetch_url", lambda url, **kwargs: fetched)

    def _must_not_be_called(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("the scheduled URL path must never touch tempfile")

    monkeypatch.setattr("tempfile.mkdtemp", _must_not_be_called)
    monkeypatch.setattr("tempfile.NamedTemporaryFile", _must_not_be_called)
    monkeypatch.setattr("tempfile.TemporaryDirectory", _must_not_be_called)

    scheduled = ScheduledIngest(
        "https://trusted.example/page",
        bundle,
        policy,
        dry_run=False,
        assume_yes=True,
        now=lambda: _ASOF,
    )
    result = scheduled.run_once()

    assert result.committed is True


# --- ambient remote generation variables never reach an injected provider --


def test_an_injected_generation_provider_ignores_poisoned_ambient_variables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A workstation can permanently export invalid remote KOSHA_GEN_* variables.
    # Production precedence is unchanged: ingest() still resolves them via
    # resolve_generation_provider() when no provider is injected. A
    # scheduled-ingest call site that explicitly injects a deterministic
    # provider -- the pattern this milestone requires for tests exercising
    # local/offline behavior -- must stay network-free regardless of what the
    # ambient environment contains.
    monkeypatch.setenv("KOSHA_GEN_BASE_URL", "https://invalid.example/v1")
    monkeypatch.setenv("KOSHA_GEN_MODEL", "ambient-model")
    monkeypatch.setenv("KOSHA_GEN_API_KEY", "ambient-secret-value")
    monkeypatch.setattr("urllib.request.urlopen", _reject_if_called)

    bundle = _seed_bundle(tmp_path)
    fetched = _raw_doc(
        "# Shipping\n\nExpedited orders ship within one business day of confirmation.\n"
    )

    result = pipeline_ingest(
        Path("scheduled-source"),
        bundle,
        asof=_ASOF,
        dry_run=False,
        assume_yes=True,
        raw_docs=[fetched],
        embedding_provider=LexicalEmbeddingProvider(),
        generation_provider=ExtractiveGenerationProvider(),
    )

    assert result.committed is True


# --- URL fetch coverage: complete, scoped to the response body only ---------


def test_a_scheduled_url_fetch_reports_complete_coverage_scoped_to_the_response_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _seed_bundle(tmp_path)
    policy = SourcePolicy(max_bytes=1_000_000, allowed_hosts=frozenset({"trusted.example"}))
    fetched = _raw_doc(
        "# Shipping\n\nExpedited orders ship within one business day of confirmation.\n"
    )
    monkeypatch.setattr("kosha.ingest.watch.fetch_url", lambda url, **kwargs: fetched)

    scheduled = ScheduledIngest(
        "https://trusted.example/page",
        bundle,
        policy,
        dry_run=True,
        now=lambda: _ASOF,
    )
    result = scheduled.run_once()

    assert result.evidence_run is not None
    coverage = result.evidence_run.run.coverage
    assert coverage.kind is CoverageKind.COMPLETE
    assert coverage.scope is not None
    assert "https://trusted.example/page" in coverage.scope


def test_a_scheduled_url_fetchs_coverage_lands_in_the_commit_change_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _seed_bundle(tmp_path)
    policy = SourcePolicy(max_bytes=1_000_000, allowed_hosts=frozenset({"trusted.example"}))
    fetched = _raw_doc(
        "# Shipping\n\nExpedited orders ship within one business day of confirmation.\n"
    )
    monkeypatch.setattr("kosha.ingest.watch.fetch_url", lambda url, **kwargs: fetched)
    store = GitStore(bundle)

    scheduled = ScheduledIngest(
        "https://trusted.example/page",
        bundle,
        policy,
        dry_run=False,
        assume_yes=True,
        now=lambda: _ASOF,
    )
    result = scheduled.run_once()

    assert result.committed is True
    assert "coverage=complete" in store.commit_message()


def test_a_scheduled_local_path_run_still_derives_its_own_folder_scoped_coverage(
    tmp_path: Path,
) -> None:
    # The local-path branch of run_once() drives ingest_folder() itself, same
    # as a direct `kosha ingest` call -- it must not silently fall back to
    # unknown just because it is reached through ScheduledIngest.
    bundle = _seed_bundle(tmp_path)
    source = tmp_path / "source"
    (source / "policies").mkdir(parents=True)
    (source / "policies" / "returns.md").write_text(
        "# Returns\n\nStandard returns are accepted within 45 days of delivery.\n",
        encoding="utf-8",
    )
    policy = SourcePolicy(max_bytes=1_000_000)
    scheduled = ScheduledIngest(source, bundle, policy, dry_run=True, now=lambda: _ASOF)
    result = scheduled.run_once()

    assert result.evidence_run is not None
    assert result.evidence_run.run.coverage.kind is CoverageKind.COMPLETE
