"""Never-silent-overwrite invariant under conflicting re-ingest (M9 PR-5).

system_design §7.1 forbids a contradiction being silently overwritten and §8.1
requires conflicting re-ingests to be resolved-or-escalated, never lost. Driving a
stream of conflicting claims through ``reconcile`` must, at every step, keep every
prior claim (retained, not deleted) and never rewrite a statement in place — the
acceptance criterion mirrored on the M7 fidelity test, for the contradiction lane.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from kosha.contradiction import (
    LexicalContradictionJudge,
    Resolution,
    assert_no_silent_overwrite,
    effective_claims,
    reconcile,
)
from kosha.merge.claims import make_claim
from kosha.model import Claim

_START = datetime(2026, 1, 1, tzinfo=UTC)
_JUDGE = LexicalContradictionJudge()
_AUTH = {"wiki": 1, "official": 3, "official-b": 3, "wiki-a": 2}
_INGESTS = 20


def _returns(days: int) -> str:
    return f"Standard returns are accepted within {days} days of delivery."


def test_temporal_re_ingest_supersedes_and_retains_every_claim() -> None:
    claims: list[Claim] = [make_claim(_returns(30), "wiki", _START, effective_from=_START)]
    original = list(claims)

    for i in range(1, _INGESTS + 1):
        effective = _START + timedelta(days=i)
        new = make_claim(_returns(30 + i), "wiki", effective, effective_from=effective)
        result = reconcile(claims, new, authority=_AUTH, judge=_JUDGE)
        assert result.conflicting is True
        assert result.outcome is not None
        assert result.outcome.resolution is Resolution.TEMPORAL
        assert_no_silent_overwrite(claims, result.claims)
        assert any(c.claim_id == new.claim_id for c in result.claims)
        claims = list(result.claims)

    # Current view is the latest only; the full history is retained, not lost.
    heads = effective_claims(claims)
    assert [c.statement for c in heads] == [_returns(50)]
    assert len(claims) == _INGESTS + 1  # 1 root + 20 supersessions, nothing deleted
    assert_no_silent_overwrite(original, claims)


def test_mixed_conflicting_stream_is_resolved_or_escalated_never_lost() -> None:
    claims: list[Claim] = [make_claim(_returns(30), "wiki", _START, effective_from=_START)]
    original = list(claims)
    introduced = {c.claim_id for c in claims}

    # Three conflicting re-ingests exercising each resolution branch in turn.
    later = _START + timedelta(days=10)
    stream = [
        make_claim(_returns(45), "wiki", later, effective_from=later),  # temporal
        make_claim(_returns(60), "official", _START),  # higher authority, no temporal
        make_claim(_returns(90), "official-b", _START),  # equal authority -> escalate
    ]
    expected = [Resolution.TEMPORAL, Resolution.AUTHORITY, Resolution.ESCALATE]

    for new, rule in zip(stream, expected, strict=True):
        result = reconcile(claims, new, authority=_AUTH, judge=_JUDGE)
        assert result.conflicting is True
        assert result.outcome is not None
        assert result.outcome.resolution is rule
        assert_no_silent_overwrite(claims, result.claims)
        introduced.add(new.claim_id)
        claims = list(result.claims)

    # Every claim ever introduced survives; the escalation held its claim aside.
    present = {c.claim_id for c in claims}
    assert introduced <= present
    assert [c.statement for c in effective_claims(claims)] == [_returns(60)]
    assert_no_silent_overwrite(original, claims)


def test_escalated_conflict_emits_a_record_and_keeps_both_claims() -> None:
    claims = [make_claim(_returns(30), "wiki-a", _START)]
    new = make_claim(_returns(60), "wiki", _START)
    result = reconcile(claims, new, authority={"wiki-a": 2, "wiki": 2}, judge=_JUDGE)
    assert result.escalated is True
    assert result.escalation is not None
    # The human plan sees both claims with provenance; neither is lost.
    assert result.escalation.old_claim.source_id == "wiki-a"
    assert result.escalation.new_claim.source_id == "wiki"
    ids = {c.claim_id for c in result.claims}
    assert claims[0].claim_id in ids
    assert new.claim_id in ids
