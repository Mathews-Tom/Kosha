"""End-to-end evidence integration: dry-run staging, durable commit, and legacy-safe
rejection (DEVELOPMENT_PLAN.md M3).

Every scenario here exercises the real ``ingest()`` / ``commit_plan()`` /
``commit_reviewed_plan()`` wiring against an injected, tmp-rooted
:class:`EvidenceStore` -- never the operator's real ``~/.kosha`` vault.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from kosha.approve import Decision, PlanRouting
from kosha.evidence import EvidenceStore
from kosha.git_store import GitStore
from kosha.ingest import ingest_folder
from kosha.pipeline import commit_reviewed_plan, ingest
from kosha.plan import build_plan

_ASOF = datetime(2026, 6, 28, tzinfo=UTC)
_EVIDENCE_TRAILER = re.compile(r"^Evidence-SHA256: (?P<digest>[0-9a-f]{64})$", re.MULTILINE)
_RUN_TRAILER = re.compile(r"^Source-Run: (?P<run_id>\S+)$", re.MULTILINE)


def _seed_bundle(tmp_path: Path) -> tuple[Path, GitStore, str]:
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
    return bundle, store, store.current_sha("main")


def _update_source(tmp_path: Path, *, name: str = "source", days: int = 60) -> Path:
    source = tmp_path / name
    (source / "policies").mkdir(parents=True)
    (source / "policies" / "returns.md").write_text(
        f"# Returns\n\nStandard returns are accepted within {days} days of delivery.\n",
        encoding="utf-8",
    )
    return source


def _contradicting_source(tmp_path: Path) -> Path:
    # Same authority (0) as the seed's hydrated claims -> escalates to BLOCK
    # rather than silently superseding, with no secret content involved.
    return _update_source(tmp_path, name="source-conflict", days=90)


# --- dry run: identity computed, nothing durable -----------------------------


def test_dry_run_computes_evidence_identity_but_writes_nothing(tmp_path: Path) -> None:
    bundle, store, _ = _seed_bundle(tmp_path)
    vault = EvidenceStore(tmp_path / "vault")
    result = ingest(
        _update_source(tmp_path),
        bundle,
        asof=_ASOF,
        dry_run=True,
        git_store=store,
        evidence_store=vault,
    )
    assert result.evidence_run is not None
    assert len(result.evidence_run.run.evidence) == 1
    assert not vault.root.exists()


# --- approved, non-dry-run commit: durable evidence + commit trailers -------


def test_an_approved_commit_persists_durable_evidence_and_commit_trailers(
    tmp_path: Path,
) -> None:
    bundle, store, _ = _seed_bundle(tmp_path)
    vault = EvidenceStore(tmp_path / "vault")
    result = ingest(
        _update_source(tmp_path),
        bundle,
        asof=_ASOF,
        source_authority=10,
        git_store=store,
        branch="ingest/evidence",
        evidence_store=vault,
    )
    assert result.committed is True
    assert result.evidence_run is not None
    digest = result.evidence_run.run.evidence[0].sha256

    message = store.commit_message()
    run_match = _RUN_TRAILER.search(message)
    assert run_match is not None
    assert run_match.group("run_id") == result.evidence_run.run.run_id
    assert _EVIDENCE_TRAILER.search(message) is not None
    assert digest in message

    loaded = vault.read_run(result.evidence_run.run.run_id)
    assert loaded.evidence[0].sha256 == digest
    assert vault.read_object(digest) == result.evidence_run.texts[digest]


def test_evidence_trailers_precede_the_reviewed_by_trailer(tmp_path: Path) -> None:
    bundle, store, _ = _seed_bundle(tmp_path)
    vault = EvidenceStore(tmp_path / "vault")
    ingest(
        _update_source(tmp_path),
        bundle,
        asof=_ASOF,
        source_authority=10,
        git_store=store,
        branch="ingest/evidence-reviewer",
        reviewer="Jane Doe <jane@example.com>",
        evidence_store=vault,
    )
    message = store.commit_message()
    assert message.index("Source-Run:") < message.index("Reviewed-by:")


# --- rejected plan: evidence identity computed, never made durable ----------


def test_a_rejected_plan_leaves_no_durable_evidence(tmp_path: Path) -> None:
    bundle, store, main_sha = _seed_bundle(tmp_path)
    vault = EvidenceStore(tmp_path / "vault")
    result = ingest(
        _contradicting_source(tmp_path),
        bundle,
        asof=_ASOF,
        git_store=store,
        branch="ingest/contradiction",
        evidence_store=vault,
    )
    assert result.routing.requires_approval is True
    assert result.decision is Decision.REJECT
    assert result.committed is False
    assert result.evidence_run is not None
    assert len(result.evidence_run.run.evidence) == 1  # identity was computed...
    assert not vault.root.exists()  # ...but never written durably
    assert store.current_sha("main") == main_sha
    assert not store.branch_exists("ingest/contradiction")


def test_an_explicitly_approved_blocked_plan_still_persists_evidence(tmp_path: Path) -> None:
    bundle, store, _ = _seed_bundle(tmp_path)
    vault = EvidenceStore(tmp_path / "vault")
    result = ingest(
        _contradicting_source(tmp_path),
        bundle,
        asof=_ASOF,
        git_store=store,
        branch="ingest/contradiction-approved",
        reader=lambda _: "y",
        evidence_store=vault,
    )
    assert result.decision is Decision.APPROVE
    assert result.committed is True
    assert vault.root.exists()
    digest = result.evidence_run.run.evidence[0].sha256  # type: ignore[union-attr]
    assert vault.read_object(digest)


# --- review flow: durable for the whole run, trailer scoped to what landed --


def test_review_flow_partial_approval_persists_the_full_run_but_scopes_the_trailer(
    tmp_path: Path,
) -> None:
    bundle, store, main_sha = _seed_bundle(tmp_path)
    vault = EvidenceStore(tmp_path / "vault")
    source = _update_source(tmp_path)
    dry = ingest(
        source, bundle, asof=_ASOF, source_authority=10, dry_run=True,
        git_store=store, evidence_store=vault,
    )
    approved_path = "policies/returns.md"
    assert len(dry.plan.changes) > 1  # index/log regen also proposed
    filtered_plan = build_plan([c for c in dry.plan.changes if c.path == approved_path])
    filtered_routing = PlanRouting(
        routes=tuple(r for r in dry.routing.routes if r.change.path == approved_path)
    )

    result = commit_reviewed_plan(
        filtered_plan,
        filtered_routing,
        bundle,
        asof=_ASOF,
        source=source,
        git_store=store,
        branch="ingest/review-partial",
        evidence_run=dry.evidence_run,
        evidence_store=vault,
    )

    assert result.committed is True
    assert vault.root.exists()
    digest = dry.evidence_run.run.evidence[0].sha256  # type: ignore[union-attr]
    assert vault.read_object(digest)
    message = store.commit_message()
    assert digest in message
    assert store.current_sha("main") == main_sha


def test_review_flow_full_rejection_leaves_no_durable_evidence(tmp_path: Path) -> None:
    bundle, store, main_sha = _seed_bundle(tmp_path)
    vault = EvidenceStore(tmp_path / "vault")
    source = _update_source(tmp_path)
    dry = ingest(
        source, bundle, asof=_ASOF, source_authority=10, dry_run=True,
        git_store=store, evidence_store=vault,
    )
    empty_plan = build_plan([])
    empty_routing = PlanRouting(routes=())

    result = commit_reviewed_plan(
        empty_plan,
        empty_routing,
        bundle,
        asof=_ASOF,
        source=source,
        git_store=store,
        branch="ingest/review-nothing",
        evidence_run=dry.evidence_run,
        evidence_store=vault,
    )

    assert result.committed is False
    assert not vault.root.exists()
    assert store.current_sha("main") == main_sha


# --- content addressing across re-ingest: old evidence is immutable ---------


def test_a_changed_source_gets_new_evidence_without_disturbing_the_old_object(
    tmp_path: Path,
) -> None:
    bundle, store, _ = _seed_bundle(tmp_path)
    vault = EvidenceStore(tmp_path / "vault")
    first = ingest(
        _update_source(tmp_path, name="source-v1", days=60),
        bundle,
        asof=_ASOF,
        source_authority=10,
        git_store=store,
        branch="ingest/v1",
        evidence_store=vault,
    )
    assert first.committed is True
    old_digest = first.evidence_run.run.evidence[0].sha256  # type: ignore[union-attr]
    old_text = vault.read_object(old_digest)

    second = ingest(
        _update_source(tmp_path, name="source-v2", days=90),
        bundle,
        asof=_ASOF,
        source_authority=10,
        git_store=store,
        branch="ingest/v2",
        evidence_store=vault,
    )
    assert second.committed is True
    new_digest = second.evidence_run.run.evidence[0].sha256  # type: ignore[union-attr]

    assert new_digest != old_digest
    assert vault.read_object(old_digest) == old_text  # untouched by the second run
    assert vault.read_object(new_digest) != old_text


# --- no duplicate fetch across the review flow -------------------------------


def test_the_review_flow_fetches_the_source_exactly_once(
    tmp_path: Path, monkeypatch
) -> None:
    bundle, store, _ = _seed_bundle(tmp_path)
    vault = EvidenceStore(tmp_path / "vault")
    source = _update_source(tmp_path)
    calls = 0
    real_ingest_folder = ingest_folder

    def _counting_ingest_folder(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return real_ingest_folder(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr("kosha.pipeline.run.ingest_folder", _counting_ingest_folder)

    dry = ingest(
        source, bundle, asof=_ASOF, source_authority=10, dry_run=True,
        git_store=store, evidence_store=vault,
    )
    approved_path = "policies/returns.md"
    filtered_plan = build_plan([c for c in dry.plan.changes if c.path == approved_path])
    filtered_routing = PlanRouting(
        routes=tuple(r for r in dry.routing.routes if r.change.path == approved_path)
    )
    commit_reviewed_plan(
        filtered_plan,
        filtered_routing,
        bundle,
        asof=_ASOF,
        source=source,
        git_store=store,
        branch="ingest/no-duplicate-fetch",
        evidence_run=dry.evidence_run,
        evidence_store=vault,
    )

    assert calls == 1


# --- unrelated claims stay byte-identical across an evidence-backed update --


def test_unrelated_claims_remain_byte_identical_across_an_evidence_backed_update(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "bundle"
    (bundle / "policies").mkdir(parents=True)
    (bundle / "policies" / "returns.md").write_text(
        "---\ntype: policy\ntitle: Returns\n"
        "description: When and how customers may return products.\n---\n"
        "Standard returns are accepted within 30 days of delivery.\n\n"
        "Gold members receive free return shipping.\n",
        encoding="utf-8",
    )
    store = GitStore.init(bundle)
    store.commit(["policies/returns.md"], "chore: seed")
    vault = EvidenceStore(tmp_path / "vault")

    source = tmp_path / "source"
    (source / "policies").mkdir(parents=True)
    (source / "policies" / "returns.md").write_text(
        "# Returns\n\nStandard returns are accepted within 60 days of delivery.\n",
        encoding="utf-8",
    )
    result = ingest(
        source,
        bundle,
        asof=_ASOF,
        source_authority=10,
        git_store=store,
        branch="ingest/unrelated-claim-stability",
        evidence_store=vault,
    )
    assert result.committed is True
    updated = (bundle / "policies" / "returns.md").read_text(encoding="utf-8")
    assert "Gold members receive free return shipping." in updated
    assert "60 days" in updated
    assert "30 days" not in updated
