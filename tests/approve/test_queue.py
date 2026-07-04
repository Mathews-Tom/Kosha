"""Shared BLOCK-lane review queue: identity, append-only history, concurrency (M9 PR-4).

``ReviewQueue`` is the persisted, multi-reviewer counterpart to the
single-reader ``request_decision``/``request_item_decisions`` gates: several
independent processes may open the same queue file and record decisions
against the same item without a lock-free race silently dropping one of
them.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from kosha.approve.autonomy import ChangeRouting, Lane, PlanRouting
from kosha.approve.decision import Decision
from kosha.approve.queue import ReviewQueue
from kosha.plan import ChangeKind, FileChange, build_plan


def _change(path: str) -> FileChange:
    return FileChange(path=path, kind=ChangeKind.CREATE, content="x")


def _routing(
    *, auto: tuple[FileChange, ...] = (), block: tuple[FileChange, ...] = ()
) -> PlanRouting:
    routes = [ChangeRouting(c, Lane.AUTO, "auto") for c in auto]
    routes += [ChangeRouting(c, Lane.BLOCK, "escalated") for c in block]
    return PlanRouting(routes=tuple(routes))


def test_enqueue_only_admits_block_lane_changes(tmp_path: Path) -> None:
    auto, blocked = _change("auto.md"), _change("blocked.md")
    plan = build_plan([auto, blocked])
    routing = _routing(auto=[auto], block=[blocked])
    queue = ReviewQueue(tmp_path / "queue.json")

    items = queue.enqueue(plan, routing, source="watch:https://trusted.example/page")

    assert [item.path for item in items] == ["blocked.md"]


def test_a_plan_with_no_block_lane_routes_enqueues_nothing(tmp_path: Path) -> None:
    auto = _change("auto.md")
    plan = build_plan([auto])
    routing = _routing(auto=[auto])
    queue = ReviewQueue(tmp_path / "queue.json")

    assert queue.enqueue(plan, routing, source="s") == []
    assert queue.items() == []


def test_enqueued_item_records_the_creators_identity_and_starts_undecided(
    tmp_path: Path,
) -> None:
    blocked = _change("blocked.md")
    plan = build_plan([blocked])
    routing = _routing(block=[blocked])
    queue = ReviewQueue(tmp_path / "queue.json")

    [item] = queue.enqueue(
        plan, routing, source="watch:https://trusted.example/page", created_by="ingest-bot"
    )

    assert item.created_by == "ingest-bot"
    assert item.decisions == ()


def test_record_decision_appends_the_reviewers_identity_to_history(tmp_path: Path) -> None:
    blocked = _change("blocked.md")
    plan = build_plan([blocked])
    routing = _routing(block=[blocked])
    queue = ReviewQueue(tmp_path / "queue.json")
    [item] = queue.enqueue(plan, routing, source="s", created_by="ingest-bot")

    queue.record_decision(item.item_id, "alice@example.com", Decision.APPROVE)
    history = queue.history(item.item_id)

    assert [(record.reviewer, record.decision) for record in history] == [
        ("alice@example.com", Decision.APPROVE)
    ]


def test_a_second_reviewers_decision_appends_rather_than_overwriting_the_first(
    tmp_path: Path,
) -> None:
    blocked = _change("blocked.md")
    plan = build_plan([blocked])
    routing = _routing(block=[blocked])
    queue = ReviewQueue(tmp_path / "queue.json")
    [item] = queue.enqueue(plan, routing, source="s", created_by="ingest-bot")

    queue.record_decision(item.item_id, "alice@example.com", Decision.REJECT)
    queue.record_decision(item.item_id, "bob@example.com", Decision.APPROVE)

    history = queue.history(item.item_id)
    assert [record.reviewer for record in history] == ["alice@example.com", "bob@example.com"]
    assert [record.decision for record in history] == [Decision.REJECT, Decision.APPROVE]
    # The item's status reflects the latest decision, not the first -- but the
    # first reviewer's action is still visible in the audit trail above.
    [persisted] = queue.items()
    assert persisted.status == Decision.APPROVE.value


def test_record_decision_on_an_unknown_item_id_raises_key_error(tmp_path: Path) -> None:
    queue = ReviewQueue(tmp_path / "queue.json")
    with pytest.raises(KeyError):
        queue.record_decision("does-not-exist", "alice@example.com", Decision.APPROVE)


def test_record_decision_requires_a_reviewer_identity(tmp_path: Path) -> None:
    blocked = _change("blocked.md")
    plan = build_plan([blocked])
    routing = _routing(block=[blocked])
    queue = ReviewQueue(tmp_path / "queue.json")
    [item] = queue.enqueue(plan, routing, source="s")

    with pytest.raises(ValueError, match="reviewer identity"):
        queue.record_decision(item.item_id, "   ", Decision.APPROVE)


def test_concurrent_reviewers_writing_to_the_same_persisted_queue_do_not_lose_decisions(
    tmp_path: Path,
) -> None:
    path = tmp_path / "queue.json"
    blocked = _change("blocked.md")
    plan = build_plan([blocked])
    routing = _routing(block=[blocked])
    [item] = ReviewQueue(path).enqueue(plan, routing, source="s", created_by="ingest-bot")

    reviewers = [f"reviewer-{i}@example.com" for i in range(12)]
    barrier = threading.Barrier(len(reviewers))
    errors: list[BaseException] = []

    def _record(reviewer: str) -> None:
        try:
            barrier.wait(timeout=5)
            # Each thread opens its own queue handle onto the same file, the
            # way independent server processes sharing the queue would.
            ReviewQueue(path).record_decision(item.item_id, reviewer, Decision.APPROVE)
        except BaseException as exc:  # re-raised on the main thread below
            errors.append(exc)

    threads = [threading.Thread(target=_record, args=(reviewer,)) for reviewer in reviewers]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert not errors
    history = ReviewQueue(path).history(item.item_id)
    assert {record.reviewer for record in history} == set(reviewers)
    assert len(history) == len(reviewers)


def test_a_duplicate_pending_source_and_path_is_not_enqueued_twice(tmp_path: Path) -> None:
    blocked = _change("blocked.md")
    plan = build_plan([blocked])
    routing = _routing(block=[blocked])
    queue = ReviewQueue(tmp_path / "queue.json")
    source = "watch:https://trusted.example/page"
    [first] = queue.enqueue(plan, routing, source=source, created_by="ingest-bot")

    second = queue.enqueue(plan, routing, source=source, created_by="ingest-bot")

    assert second == []
    [persisted] = queue.items()
    assert persisted.item_id == first.item_id


def test_the_same_source_and_path_enqueues_again_once_no_longer_pending(
    tmp_path: Path,
) -> None:
    # Only a still-pending item blocks a re-enqueue: once a reviewer has acted,
    # a later scheduled run for the same (source, path) must be able to queue
    # a fresh item rather than being silently swallowed forever.
    blocked = _change("blocked.md")
    plan = build_plan([blocked])
    routing = _routing(block=[blocked])
    queue = ReviewQueue(tmp_path / "queue.json")
    source = "watch:https://trusted.example/page"
    [first] = queue.enqueue(plan, routing, source=source, created_by="ingest-bot")
    queue.record_decision(first.item_id, "alice@example.com", Decision.REJECT)

    second = queue.enqueue(plan, routing, source=source, created_by="ingest-bot")

    assert len(second) == 1
    assert second[0].item_id != first.item_id
    assert {item.item_id for item in queue.items()} == {first.item_id, second[0].item_id}


def test_items_on_a_never_persisted_queue_does_not_create_the_queue_file(
    tmp_path: Path,
) -> None:
    # A read-only listing (e.g. ``kosha review-queue list`` against a bundle
    # that has never had a BLOCK-lane escalation) must stay read-only: it must
    # never conjure an empty queue.json into existence on disk.
    path = tmp_path / "queue.json"
    queue = ReviewQueue(path)

    assert queue.items() == []
    assert not path.exists()


def test_items_never_writes_to_an_already_persisted_queue_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    blocked = _change("blocked.md")
    queue = ReviewQueue(tmp_path / "queue.json")
    queue.enqueue(build_plan([blocked]), _routing(block=(blocked,)), source="watch")

    def _no_write(*_args: object, **_kwargs: object) -> int:
        raise AssertionError("items() must not rewrite the persisted queue file")

    monkeypatch.setattr(Path, "write_text", _no_write)

    assert len(queue.items()) == 1


def test_history_never_writes_to_the_persisted_queue_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    blocked = _change("blocked.md")
    queue = ReviewQueue(tmp_path / "queue.json")
    [item] = queue.enqueue(build_plan([blocked]), _routing(block=(blocked,)), source="watch")

    def _no_write(*_args: object, **_kwargs: object) -> int:
        raise AssertionError("history() must not rewrite the persisted queue file")

    monkeypatch.setattr(Path, "write_text", _no_write)

    assert queue.history(item.item_id) == []
