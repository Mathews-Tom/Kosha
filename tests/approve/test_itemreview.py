"""Per-item review: approve/reject each plan item individually (M8 PR-3).

Mirrors the blanket gate's default-safe contract (``tests/pipeline/test_approve.py``)
at item granularity: an unparseable/EOF/empty answer rejects only that item, and
any unacknowledged escalated flag withholds the whole plan rather than a subset.
"""

from __future__ import annotations

from collections.abc import Iterator

from kosha.approve import ChangeRouting, Decision, Lane, PlanRouting, request_item_decisions
from kosha.approve.decision import Reader
from kosha.plan import ChangeKind, FileChange, Flag, build_plan


def _change(path: str) -> FileChange:
    return FileChange(path=path, kind=ChangeKind.CREATE, content="x")


def _routing(*changes: FileChange) -> PlanRouting:
    return PlanRouting(routes=tuple(ChangeRouting(c, Lane.AUTO, "auto") for c in changes))


def _reader(answers: list[str]) -> Reader:
    it: Iterator[str] = iter(answers)

    def read(_prompt: str) -> str:
        return next(it)

    return read


def _noop(_line: str) -> None:
    return None


def test_approves_some_items_and_rejects_others() -> None:
    a, b = _change("a.md"), _change("b.md")
    plan = build_plan([a, b])
    result = request_item_decisions(plan, _routing(a, b), _reader(["y", "n"]), printer=_noop)
    assert result.change_decisions == {"a.md": Decision.APPROVE, "b.md": Decision.REJECT}
    assert result.approved_paths() == frozenset({"a.md"})
    assert result.proceeds is True


def test_unparseable_answer_defaults_to_reject_for_that_item_only() -> None:
    a, b = _change("a.md"), _change("b.md")
    plan = build_plan([a, b])
    # request_decision retries up to 3 times per item before defaulting reject.
    result = request_item_decisions(
        plan, _routing(a, b), _reader(["huh", "huh", "huh", "y"]), printer=_noop
    )
    assert result.change_decisions["a.md"] is Decision.REJECT
    assert result.change_decisions["b.md"] is Decision.APPROVE


def test_all_rejected_does_not_proceed() -> None:
    a = _change("a.md")
    plan = build_plan([a])
    result = request_item_decisions(plan, _routing(a), _reader(["n"]), printer=_noop)
    assert result.approved_paths() == frozenset()
    assert result.proceeds is False


def test_unacknowledged_flag_withholds_the_whole_plan_even_if_changes_approved() -> None:
    a = _change("a.md")
    plan = build_plan([a], [Flag(concept_id="c", summary="conflict")])
    # flag rejected first ("n"), then the change approved ("y") -- still withheld.
    result = request_item_decisions(plan, _routing(a), _reader(["n", "y"]), printer=_noop)
    assert result.flags_acknowledged is False
    assert result.approved_paths() == frozenset()
    assert result.proceeds is False


def test_acknowledged_flag_lets_approved_changes_proceed() -> None:
    a = _change("a.md")
    plan = build_plan([a], [Flag(concept_id="c", summary="conflict")])
    result = request_item_decisions(plan, _routing(a), _reader(["y", "y"]), printer=_noop)
    assert result.flags_acknowledged is True
    assert result.approved_paths() == frozenset({"a.md"})
    assert result.proceeds is True


def test_eof_rejects_without_raising() -> None:
    a = _change("a.md")
    plan = build_plan([a])

    def closed(_: str) -> str:
        raise EOFError

    result = request_item_decisions(plan, _routing(a), closed, printer=_noop)
    assert result.change_decisions["a.md"] is Decision.REJECT


def test_printer_receives_one_render_per_item() -> None:
    a, b = _change("a.md"), _change("b.md")
    plan = build_plan([a, b])
    printed: list[str] = []
    request_item_decisions(plan, _routing(a, b), _reader(["y", "y"]), printer=printed.append)
    assert len(printed) == 2
    assert "a.md" in printed[0]
    assert "b.md" in printed[1]


def test_empty_plan_produces_no_decisions() -> None:
    result = request_item_decisions(build_plan([]), _routing(), _reader([]), printer=_noop)
    assert result.change_decisions == {}
    assert result.proceeds is False
