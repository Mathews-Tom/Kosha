"""Pipeline wiring: writer composition + decision gate (M10 PR-5)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from kosha.approve import Decision, route_plan
from kosha.contradiction.detect import LexicalContradictionJudge
from kosha.extract import ConceptDraft
from kosha.git_store import GitStore
from kosha.merge.claims import current_claims
from kosha.merge.create import create_concept
from kosha.merge.update import LexicalClaimTargeter
from kosha.model import ClaimStatus, Concept, Frontmatter, Source, SourceKind
from kosha.pipeline import decide_plan, hydrate_claims, ingest, new_concept_id
from kosha.pipeline.writer import apply_update
from kosha.plan import ChangeKind, ContradictionState, FileChange, Flag, build_plan
from kosha.telemetry import InMemoryTelemetrySink

_ASOF = datetime(2026, 6, 28, tzinfo=UTC)
_JUDGE = LexicalContradictionJudge()
_TARGETER = LexicalClaimTargeter()


def _source(source_id: str, *, authority: int = 0) -> Source:
    return Source(
        source_id=source_id, kind=SourceKind.MARKDOWN, location=source_id, authority_rank=authority
    )


def _draft(title: str, body: str, source_id: str, *, type_: str = "policy") -> ConceptDraft:
    return ConceptDraft(title=title, body=body, description=title, type=type_, source_id=source_id)


def _returns_concept() -> Concept:
    draft = _draft(
        "Returns",
        "Standard returns are accepted within 30 days of delivery.\n\n"
        "Gold members receive free return shipping.",
        "incumbent",
    )
    return create_concept(draft, "policies/returns", _source("incumbent"), _ASOF)


# --- decide_plan -----------------------------------------------------------


def _plan(*, escalated: bool = False):
    flags = [Flag(concept_id="c", summary="x")] if escalated else []
    return build_plan([FileChange(path="a.md", kind=ChangeKind.CREATE, content="x")], flags)


def test_decide_plan_auto_skim_is_approved_without_a_reader() -> None:
    routing = route_plan(_plan())
    assert routing.requires_approval is False
    assert decide_plan(routing) is Decision.APPROVE


def test_decide_plan_block_needs_explicit_yes() -> None:
    routing = route_plan(_plan(escalated=True))
    assert routing.requires_approval is True
    assert decide_plan(routing) is Decision.REJECT  # no reader, no --yes
    assert decide_plan(routing, assume_yes=True) is Decision.APPROVE
    assert decide_plan(routing, reader=lambda _: "y") is Decision.APPROVE
    assert decide_plan(routing, reader=lambda _: "n") is Decision.REJECT


# --- hydrate_claims --------------------------------------------------------


def test_hydrate_seeds_claims_from_a_disk_loaded_body() -> None:
    concept = Concept(
        concept_id="policies/returns",
        frontmatter=Frontmatter(type="policy", description="Returns policy."),
        body="Standard returns are accepted within 30 days.\n\nGold members get free shipping.",
    )
    hydrated = hydrate_claims(concept, asserted_at=_ASOF)
    assert [c.statement for c in hydrated.claims] == [
        "Standard returns are accepted within 30 days.",
        "Gold members get free shipping.",
    ]
    assert all(c.source_id == "bundle:policies/returns" for c in hydrated.claims)


def test_hydrate_is_a_noop_when_claims_exist() -> None:
    concept = _returns_concept()
    assert hydrate_claims(concept, asserted_at=_ASOF) is concept


# --- new_concept_id --------------------------------------------------------


def test_new_concept_id_uses_source_dir_and_title_slug() -> None:
    source = _source("entities/membership-tier.md")
    draft = _draft("Membership Tier", "body", "entities/membership-tier.md", type_="entity")
    assert new_concept_id(draft, source, taken=set()) == "entities/membership-tier"


def test_new_concept_id_rejects_an_existing_target() -> None:
    source = _source("policies/returns.md")
    draft = _draft("Returns", "body", "policies/returns.md")
    with pytest.raises(ValueError, match="already exists"):
        new_concept_id(draft, source, taken={"policies/returns"})


# --- apply_update ----------------------------------------------------------


def test_update_resolves_numeric_conflict_by_authority_new_wins() -> None:
    existing = _returns_concept()
    draft = _draft("Returns", "Standard returns are accepted within 60 days of delivery.", "update")
    result = apply_update(
        existing,
        draft,
        _source("update", authority=10),
        _ASOF,
        authority={"update": 10},
        targeter=_TARGETER,
        judge=_JUDGE,
    )
    statements = [c.statement for c in current_claims(result.concept.claims)]
    assert "Standard returns are accepted within 60 days of delivery." in statements
    assert "Gold members receive free return shipping." in statements
    assert all("30 days" not in s for s in statements)
    # The retired claim is kept, not deleted.
    assert any(
        c.status is ClaimStatus.CONTRADICTED and "30 days" in c.statement
        for c in result.concept.claims
    )
    assert result.superseded is True
    assert result.contradiction is ContradictionState.RESOLVED
    assert result.escalations == ()


def test_update_escalates_equal_authority_conflict_and_holds_new() -> None:
    existing = _returns_concept()
    draft = _draft("Returns", "Standard returns are accepted within 60 days of delivery.", "update")
    result = apply_update(
        existing,
        draft,
        _source("update", authority=0),
        _ASOF,
        authority={},
        targeter=_TARGETER,
        judge=_JUDGE,
    )
    statements = [c.statement for c in current_claims(result.concept.claims)]
    # Unresolved: the incumbent stays in force, the new claim is held contradicted.
    assert "Standard returns are accepted within 30 days of delivery." in statements
    assert "Standard returns are accepted within 60 days of delivery." not in statements
    assert result.contradiction is ContradictionState.ESCALATED
    assert len(result.escalations) == 1


def test_update_appends_a_novel_statement_without_superseding() -> None:
    existing = _returns_concept()
    draft = _draft("Returns", "Returns require the original packaging intact.", "update")
    result = apply_update(
        existing,
        draft,
        _source("update", authority=10),
        _ASOF,
        authority={"update": 10},
        targeter=_TARGETER,
        judge=_JUDGE,
    )
    statements = [c.statement for c in current_claims(result.concept.claims)]
    assert "Returns require the original packaging intact." in statements
    assert "Standard returns are accepted within 30 days of delivery." in statements
    assert result.superseded is False
    assert result.contradiction is ContradictionState.NONE


def test_update_verbatim_reassert_is_a_noop() -> None:
    existing = _returns_concept()
    draft = _draft("Returns", "Gold members receive free return shipping.", "update")
    result = apply_update(
        existing,
        draft,
        _source("update", authority=10),
        _ASOF,
        authority={"update": 10},
        targeter=_TARGETER,
        judge=_JUDGE,
    )
    assert result.superseded is False
    assert len(result.concept.claims) == len(existing.claims)


# --- end-to-end ingest -----------------------------------------------------


def _seed_bundle(tmp_path: Path) -> tuple[Path, GitStore, str]:
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
    return bundle, store, store.current_sha("main")


def _policy_update_source(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    (source / "policies").mkdir(parents=True)
    (source / "policies" / "returns.md").write_text(
        "# Returns\n\nStandard returns are accepted within 60 days of delivery.\n",
        encoding="utf-8",
    )
    return source


def test_dry_run_builds_a_plan_without_committing(tmp_path: Path) -> None:
    bundle, store, main_sha = _seed_bundle(tmp_path)
    result = ingest(
        _policy_update_source(tmp_path),
        bundle,
        asof=_ASOF,
        source_authority=10,
        dry_run=True,
        git_store=store,
    )
    assert any(c.path == "policies/returns.md" for c in result.plan.updates)
    assert result.committed is False
    assert result.decision is None
    assert store.current_sha("main") == main_sha
    assert store.head_branch() == "main"


def test_ingest_emits_route_and_decision_telemetry_without_source_body(tmp_path: Path) -> None:
    bundle, store, _ = _seed_bundle(tmp_path)
    sink = InMemoryTelemetrySink()

    ingest(
        _policy_update_source(tmp_path),
        bundle,
        asof=_ASOF,
        source_authority=10,
        dry_run=True,
        git_store=store,
        telemetry_sink=sink,
    )

    kinds = [record["kind"] for record in sink.records]
    assert "provider" in kinds
    assert "decision" in kinds
    assert "route" in kinds
    assert any(record.get("outcome") == "update" for record in sink.records)
    assert all("confidence" in record for record in sink.records if record["kind"] == "route")
    assert all("body" not in record and "text" not in record for record in sink.records)


def test_ingest_commits_an_approved_plan_on_a_branch(tmp_path: Path) -> None:
    bundle, store, main_sha = _seed_bundle(tmp_path)
    result = ingest(
        _policy_update_source(tmp_path),
        bundle,
        asof=_ASOF,
        source_authority=10,
        git_store=store,
        branch="ingest/test",
    )
    assert result.committed is True
    assert result.branch == "ingest/test"
    assert store.head_branch() == "ingest/test"
    assert "policies/returns.md" in store.tracked_files()
    assert store.current_sha("main") == main_sha  # main never moved
    assert store.tag_exists("backup/2026-06-28")


def test_ingest_with_a_reviewer_records_a_reviewed_by_trailer(tmp_path: Path) -> None:
    bundle, store, _ = _seed_bundle(tmp_path)
    result = ingest(
        _policy_update_source(tmp_path),
        bundle,
        asof=_ASOF,
        source_authority=10,
        git_store=store,
        branch="ingest/reviewed",
        reviewer="Jane Doe <jane@example.com>",
    )
    assert result.committed is True
    assert result.reviewer == "Jane Doe <jane@example.com>"
    assert "Reviewed-by: Jane Doe <jane@example.com>" in store.commit_message()


def test_ingest_without_a_reviewer_carries_no_trailer(tmp_path: Path) -> None:
    bundle, store, _ = _seed_bundle(tmp_path)
    result = ingest(
        _policy_update_source(tmp_path),
        bundle,
        asof=_ASOF,
        source_authority=10,
        git_store=store,
        branch="ingest/unreviewed",
    )
    assert result.committed is True
    assert result.reviewer is None
    assert "Reviewed-by:" not in store.commit_message()


def test_ingest_rejects_a_reviewer_identity_with_an_embedded_newline(tmp_path: Path) -> None:
    bundle, store, _ = _seed_bundle(tmp_path)
    with pytest.raises(ValueError, match="newline"):
        ingest(
            _policy_update_source(tmp_path),
            bundle,
            asof=_ASOF,
            source_authority=10,
            git_store=store,
            branch="ingest/forged",
            reviewer="Jane Doe\nReviewed-by: Forged Identity",
        )
    assert not store.branch_exists("ingest/forged")
