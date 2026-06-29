"""The auditability / guarantee acceptance axis (spike S2, Track D).

This exercises, end-to-end, the loop's BINARY capability a prompt cannot match at
any rate — the governance argument §2.4 calls "a guarantee, not a quality win":

* a **verifiable no-silent-overwrite guarantee** — reconciling every held-out
  contradiction never drops or rewrites a prior claim (``assert_no_silent_overwrite``);
* a **complete, replayable provenance trail** — the claim supersede lineage
  retains the retired ancestor and reconstructs the current head, and every ingest
  lands on its own Git branch (``git_store`` branch-per-ingest) leaving ``main``
  untouched, so the prior state stays recoverable from history.

A prompt-only baseline produces freehand text: it can flag a conflict but offers
no machine-verifiable guarantee and no per-change branch/claim trail to replay.
This axis therefore measures the *existing* guarantee; it builds no new compliance
features. The Gate-0 v2 criterion treats it as a necessary condition, never a
quality win that could carry a GO on its own.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from kosha.bench.gate2.contradictions import ContradictionCase
from kosha.contradiction import (
    LexicalContradictionJudge,
    SilentOverwriteError,
    assert_no_silent_overwrite,
    reconcile,
)
from kosha.git_store import GitStore
from kosha.merge import make_claim
from kosha.merge.claims import current_claims
from kosha.model import ClaimStatus
from kosha.okf import load_bundle
from kosha.pipeline import ingest
from kosha.providers.extractive import ExtractiveGenerationProvider
from kosha.providers.lexical import LexicalEmbeddingProvider

_PRIOR_ASOF = datetime(2026, 1, 1, tzinfo=UTC)
_NEW_ASOF = datetime(2027, 1, 1, tzinfo=UTC)
_INGEST_ASOF = datetime(2026, 6, 28, tzinfo=UTC)
_INGEST_BRANCH = "ingest/policy-update"

_SEED_RETURNS = """---
type: policy
title: Returns
description: When and how customers may return products.
---
Standard returns are accepted within 30 days of delivery.

Gold members receive free return shipping.
"""
_SEED_REFUNDS = """---
type: policy
title: Refunds
description: How refunds are processed.
---
Refunds post to the original payment card after approval.
"""
_SOURCE_RETURNS = "# Returns\n\nStandard returns are accepted within 60 days of delivery.\n"


@dataclass(frozen=True)
class AuditabilityResult:
    """The loop's measured guarantee + provenance trail (a binary acceptance axis)."""

    guarantee_cases: int
    guarantee_violations: int
    supersede_lineage_ok: bool
    branch_per_ingest_ok: bool

    @property
    def guarantee_verified(self) -> bool:
        return self.guarantee_cases > 0 and self.guarantee_violations == 0

    @property
    def provenance_replayable(self) -> bool:
        return self.supersede_lineage_ok and self.branch_per_ingest_ok

    @property
    def verified(self) -> bool:
        return self.guarantee_verified and self.provenance_replayable


def verify_guarantee(cases: Sequence[ContradictionCase]) -> tuple[int, int]:
    """Reconcile every held-out contradiction; return (checked, silent-overwrite violations).

    A deterministic judge is used so the guarantee is exercised provider-
    independently: whatever the verdict, reconciliation must never drop or rewrite
    the prior claim.
    """
    judge = LexicalContradictionJudge()
    checked = violations = 0
    for case in cases:
        old = make_claim(case.prior, "corpus", _PRIOR_ASOF, effective_from=_PRIOR_ASOF)
        new = make_claim(case.new, "update", _NEW_ASOF, effective_from=_NEW_ASOF)
        result = reconcile([old], new, authority={"corpus": 1, "update": 1}, judge=judge)
        checked += 1
        try:
            assert_no_silent_overwrite([old], result.claims)
        except SilentOverwriteError:
            violations += 1
    return checked, violations


def verify_supersede_lineage() -> bool:
    """Exercise the supersede path: a retired ancestor retained, the head reconstructed."""
    old = make_claim(
        "Standard returns are accepted within 30 days of delivery.",
        "corpus",
        _PRIOR_ASOF,
        effective_from=_PRIOR_ASOF,
    )
    new = make_claim(
        "Standard returns are accepted within 60 days of delivery.",
        "update",
        _NEW_ASOF,
        effective_from=_NEW_ASOF,
    )
    result = reconcile(
        [old], new, authority={"corpus": 0, "update": 10}, judge=LexicalContradictionJudge()
    )
    heads = current_claims(result.claims)
    retired_retained = any(
        claim.status is not ClaimStatus.CURRENT and "30 days" in claim.statement
        for claim in result.claims
    )
    head_is_new = any("60 days" in claim.statement for claim in heads)
    chained = any(claim.supersedes is not None for claim in result.claims)
    try:
        assert_no_silent_overwrite([old], result.claims)
        no_overwrite = True
    except SilentOverwriteError:
        no_overwrite = False
    return retired_retained and head_is_new and chained and no_overwrite


def verify_branch_per_ingest(work_dir: Path) -> bool:
    """Run a real UPDATE ingest on a Git store; verify branch-per-ingest replay.

    The update lands on its own branch with ``main`` untouched, so the prior fact
    stays recoverable from history (the system of record) while the new state is
    gated for review.
    """
    bundle_root = work_dir / "bundle"
    (bundle_root / "policies").mkdir(parents=True, exist_ok=True)
    (bundle_root / "policies" / "returns.md").write_text(_SEED_RETURNS, encoding="utf-8")
    (bundle_root / "policies" / "refunds.md").write_text(_SEED_REFUNDS, encoding="utf-8")
    store = GitStore.init(bundle_root)
    seed = [path.relative_to(bundle_root).as_posix() for path in sorted(bundle_root.rglob("*.md"))]
    store.commit(seed, "chore: seed bundle")
    main_sha = store.current_sha("main")

    source = work_dir / "source" / "policies"
    source.mkdir(parents=True, exist_ok=True)
    (source / "returns.md").write_text(_SOURCE_RETURNS, encoding="utf-8")
    result = ingest(
        work_dir / "source",
        bundle_root,
        asof=_INGEST_ASOF,
        source_authority=10,
        assume_yes=True,
        git_store=store,
        branch=_INGEST_BRANCH,
        embedding_provider=LexicalEmbeddingProvider(),
        generation_provider=ExtractiveGenerationProvider(),
    )
    branch_landed = (
        result.committed
        and store.branch_exists(_INGEST_BRANCH)
        and store.head_branch() == _INGEST_BRANCH
        and store.current_sha("main") == main_sha
    )
    returns = load_bundle(bundle_root).concepts["policies/returns"]
    superseded_in_projection = "60 days" in returns.body and "30 days" not in returns.body
    replayable = bool(store.tracked_files(_INGEST_BRANCH))
    return branch_landed and superseded_in_projection and replayable


def run_auditability(cases: Sequence[ContradictionCase], *, work_dir: Path) -> AuditabilityResult:
    """Exercise the guarantee + provenance trail end-to-end and return the result."""
    checked, violations = verify_guarantee(cases)
    return AuditabilityResult(
        guarantee_cases=checked,
        guarantee_violations=violations,
        supersede_lineage_ok=verify_supersede_lineage(),
        branch_per_ingest_ok=verify_branch_per_ingest(work_dir),
    )
