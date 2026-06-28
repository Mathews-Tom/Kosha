"""Plan assembly: ordering, partitioning, and duplicate rejection (M10 PR-2)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from kosha.plan import (
    ChangeKind,
    ChangePlan,
    ContradictionState,
    FileChange,
    Flag,
    Impact,
    build_plan,
)


def _change(path: str, kind: ChangeKind = ChangeKind.CREATE, **kw: object) -> FileChange:
    return FileChange(path=path, kind=kind, content=f"# {path}\n", **kw)


def test_file_change_defaults_are_deterministic_low_impact() -> None:
    change = _change("entities/order.md", concept_id="entities/order")
    assert change.confidence == 1.0
    assert change.impact is Impact.LOW
    assert change.contradiction is ContradictionState.NONE


def test_confidence_out_of_range_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _change("a.md", confidence=1.5)


def test_build_plan_orders_changes_by_path_and_flags_by_concept() -> None:
    plan = build_plan(
        [_change("policies/returns.md", ChangeKind.UPDATE), _change("entities/order.md")],
        [Flag(concept_id="z", summary="late"), Flag(concept_id="a", summary="early")],
    )
    assert plan.paths() == ["entities/order.md", "policies/returns.md"]
    assert [f.concept_id for f in plan.flags] == ["a", "z"]


def test_build_plan_partitions_creates_and_updates() -> None:
    plan = build_plan(
        [
            _change("entities/order.md", ChangeKind.CREATE),
            _change("policies/returns.md", ChangeKind.UPDATE),
        ]
    )
    assert [c.path for c in plan.creates] == ["entities/order.md"]
    assert [c.path for c in plan.updates] == ["policies/returns.md"]


def test_build_plan_rejects_two_changes_to_one_path() -> None:
    with pytest.raises(ValueError, match="duplicate change"):
        build_plan([_change("policies/returns.md"), _change("policies/returns.md")])


def test_empty_plan_is_empty() -> None:
    assert ChangePlan().is_empty
    assert not build_plan([_change("a.md")]).is_empty
    assert not build_plan([], [Flag(concept_id="a", summary="conflict")]).is_empty
