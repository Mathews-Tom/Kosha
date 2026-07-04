"""Approve gate: plan render + default-safe decision capture (M10 PR-3)."""

from __future__ import annotations

import pytest

from kosha.approve import (
    Decision,
    Reader,
    normalize_reviewer,
    parse_decision,
    render_plan,
    request_decision,
)
from kosha.plan import (
    ChangeKind,
    ChangePlan,
    ContradictionState,
    FileChange,
    Flag,
    Impact,
    build_plan,
)


def _reader(answers: list[str]) -> Reader:
    it = iter(answers)

    def read(_: str) -> str:
        return next(it)

    return read


def _plan() -> ChangePlan:
    return build_plan(
        [
            FileChange(
                path="policies/returns.md",
                kind=ChangeKind.UPDATE,
                content="x",
                summary="returns window 30->60 days",
                concept_id="policies/returns",
                confidence=0.5,
                impact=Impact.MEDIUM,
                contradiction=ContradictionState.RESOLVED,
            ),
            FileChange(
                path="entities/membership-tier.md",
                kind=ChangeKind.CREATE,
                content="y",
                summary="new entity: membership tier",
                concept_id="entities/membership-tier",
            ),
        ],
        [Flag(concept_id="policies/refunds", summary="equal-authority conflict")],
    )


def test_render_lists_changes_flags_and_provenance() -> None:
    text = render_plan(_plan())
    assert "2 change(s), 1 flag(s)" in text
    assert "[update] policies/returns.md" in text
    assert "[create] entities/membership-tier.md" in text
    assert "returns window 30->60 days" in text
    assert "contradiction=resolved" in text
    assert "impact=medium" in text
    assert "Flags (need human judgment):" in text
    assert "policies/refunds: equal-authority conflict" in text


def test_render_empty_plan() -> None:
    assert render_plan(ChangePlan()) == "Change plan: no changes."


def test_parse_decision_yes_no_and_unknown() -> None:
    assert parse_decision("y") is Decision.APPROVE
    assert parse_decision("YES") is Decision.APPROVE
    assert parse_decision("n") is Decision.REJECT
    assert parse_decision(" No ") is Decision.REJECT
    assert parse_decision("") is None
    assert parse_decision("maybe") is None


def test_request_decision_approves_on_yes() -> None:
    assert request_decision(_reader(["y"])) is Decision.APPROVE


def test_request_decision_rejects_on_no() -> None:
    assert request_decision(_reader(["n"])) is Decision.REJECT


def test_request_decision_reprompts_then_approves() -> None:
    assert request_decision(_reader(["", "huh", "yes"])) is Decision.APPROVE


def test_request_decision_defaults_to_reject_after_retries() -> None:
    assert request_decision(_reader(["", "", ""]), retries=3) is Decision.REJECT


def test_request_decision_rejects_on_closed_input() -> None:
    def closed(_: str) -> str:
        raise EOFError

    assert request_decision(closed) is Decision.REJECT


def test_normalize_reviewer_none_stays_none() -> None:
    assert normalize_reviewer(None) is None


def test_normalize_reviewer_blank_becomes_none() -> None:
    assert normalize_reviewer("   ") is None


def test_normalize_reviewer_strips_whitespace() -> None:
    assert normalize_reviewer("  Jane Doe <jane@example.com>  ") == "Jane Doe <jane@example.com>"


def test_normalize_reviewer_rejects_embedded_newline() -> None:
    with pytest.raises(ValueError, match="newline"):
        normalize_reviewer("Jane Doe\nReviewed-by: Forged Identity")


def test_normalize_reviewer_rejects_embedded_carriage_return() -> None:
    with pytest.raises(ValueError, match="newline"):
        normalize_reviewer("Jane Doe\rReviewed-by: Forged Identity")
