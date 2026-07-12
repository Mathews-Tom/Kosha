"""Dependency-free polling watcher over bundle revisions (M8 PR-2).

``poll_once`` is exercised synchronously (no thread, no sleep) for the
no-op/failed/isolated-multi-bundle behavior; ``start``/``stop`` are exercised
with a real background thread, synchronized deterministically via
``threading.Event`` rather than a fixed sleep.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from kosha.index.embedding import EmbeddingIndex
from kosha.mcp.service import KoshaKnowledgeService
from kosha.okf.load import load_bundle
from kosha.providers import LexicalEmbeddingProvider
from kosha.server.registry import BundleRegistration, BundleRegistry
from kosha.server.revision import ActivationEvent
from kosha.server.watcher import BundleWatcher


def _write_concept(root: Path, *, title: str = "Example") -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "concept.md").write_text(
        f'---\ntype: "policy"\ntitle: {title}\n---\nBody text.\n', encoding="utf-8"
    )


def _service(bundle_root: Path) -> KoshaKnowledgeService:
    bundle = load_bundle(bundle_root)
    index = EmbeddingIndex.build(bundle, LexicalEmbeddingProvider())
    return KoshaKnowledgeService(bundle, index)


def test_poll_once_no_op_never_invokes_the_activation_callback(tmp_path: Path) -> None:
    root = tmp_path / "bundle"
    _write_concept(root)
    registry = BundleRegistry([BundleRegistration("b", _service(root))])
    events: list[ActivationEvent] = []
    watcher = BundleWatcher(registry, on_activation=events.append)

    outcomes = watcher.poll_once()

    assert len(outcomes) == 1
    assert outcomes[0].changed is False
    assert events == []


def test_poll_once_refreshes_a_changed_bundle_and_fires_the_callback_after_activation(
    tmp_path: Path,
) -> None:
    root = tmp_path / "bundle"
    _write_concept(root, title="Before")
    registry = BundleRegistry([BundleRegistration("b", _service(root))])
    before = registry.active_registration("b")
    events: list[ActivationEvent] = []
    watcher = BundleWatcher(registry, on_activation=events.append)

    _write_concept(root, title="After")
    (outcome,) = watcher.poll_once()

    assert outcome.changed is True
    assert len(events) == 1
    assert events[0].bundle_id == "b"
    assert events[0].revision == outcome.revision
    assert registry.active_registration("b") is not before


def test_poll_once_never_fires_the_callback_for_a_failed_refresh(tmp_path: Path) -> None:
    root = tmp_path / "bundle"
    _write_concept(root, title="Good")
    registry = BundleRegistry([BundleRegistration("b", _service(root))])
    events: list[ActivationEvent] = []
    watcher = BundleWatcher(registry, on_activation=events.append)

    (root / "concept.md").write_text("not frontmatter\n", encoding="utf-8")
    (outcome,) = watcher.poll_once()

    assert outcome.changed is False
    assert outcome.health == "failed"
    assert events == []


def test_poll_once_isolates_multiple_watched_bundles(tmp_path: Path) -> None:
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    _write_concept(root_a, title="A before")
    _write_concept(root_b, title="B before")
    registry = BundleRegistry(
        [
            BundleRegistration("a", _service(root_a)),
            BundleRegistration("b", _service(root_b)),
        ]
    )
    events: list[ActivationEvent] = []
    watcher = BundleWatcher(registry, on_activation=events.append)

    _write_concept(root_a, title="A after")  # only "a" changes
    outcomes = watcher.poll_once()

    outcomes_by_id = {outcome.bundle_id: outcome for outcome in outcomes}
    assert outcomes_by_id["a"].changed is True
    assert outcomes_by_id["b"].changed is False
    assert [event.bundle_id for event in events] == ["a"]


def test_poll_once_defaults_to_watching_every_registered_bundle(tmp_path: Path) -> None:
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    _write_concept(root_a)
    _write_concept(root_b)
    registry = BundleRegistry(
        [
            BundleRegistration("a", _service(root_a)),
            BundleRegistration("b", _service(root_b)),
        ]
    )
    watcher = BundleWatcher(registry)
    assert watcher.bundle_ids == ("a", "b")


def test_start_runs_poll_once_on_an_interval_until_stopped(tmp_path: Path) -> None:
    root = tmp_path / "bundle"
    _write_concept(root, title="Before")
    registry = BundleRegistry([BundleRegistration("b", _service(root))])
    activated = threading.Event()
    events: list[ActivationEvent] = []

    def _on_activation(event: ActivationEvent) -> None:
        events.append(event)
        activated.set()

    watcher = BundleWatcher(registry, on_activation=_on_activation)
    _write_concept(root, title="After")
    watcher.start(interval_seconds=0.01)
    try:
        assert activated.wait(timeout=5), "watcher never activated the changed bundle"
    finally:
        watcher.stop()

    assert len(events) == 1
    assert registry.active_registration("b").revision == events[0].revision


def test_start_twice_without_stop_raises(tmp_path: Path) -> None:
    root = tmp_path / "bundle"
    _write_concept(root)
    registry = BundleRegistry([BundleRegistration("b", _service(root))])
    watcher = BundleWatcher(registry)
    watcher.start(interval_seconds=1)
    try:
        with pytest.raises(RuntimeError, match="already started"):
            watcher.start(interval_seconds=1)
    finally:
        watcher.stop()
