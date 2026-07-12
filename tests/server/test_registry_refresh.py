"""Atomic bundle revision activation (M8 PR-1).

Covers the source spec §15 refresh algorithm end to end: no-op detection,
successful atomic activation, every candidate-construction failure stage,
concurrent-read consistency, ACL persistence across refresh, multi-bundle
isolation, and that a failed refresh's error metadata never carries source
or concept body text.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from kosha.index.embedding import EmbeddingIndex
from kosha.mcp.service import AccessDeniedError, KoshaKnowledgeService
from kosha.model import Bundle
from kosha.okf.load import load_bundle
from kosha.providers import LexicalEmbeddingProvider
from kosha.providers.base import Vector
from kosha.server.registry import BundleRegistration, BundleRegistry

CONCEPT_ID = "concept"


def _write_concept(
    root: Path,
    *,
    title: str = "Example",
    concept_type: str = "policy",
    body: str = "Body text.",
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "concept.md").write_text(
        f'---\ntype: "{concept_type}"\ntitle: {title}\n---\n{body}\n', encoding="utf-8"
    )


def _service(
    bundle: Bundle, *, bundle_access: str | None = None, clearance: tuple[str, ...] = ()
) -> KoshaKnowledgeService:
    index = EmbeddingIndex.build(bundle, LexicalEmbeddingProvider())
    return KoshaKnowledgeService(bundle, index, bundle_access=bundle_access, clearance=clearance)


def _registry(
    root: Path, *, bundle_access: str | None = None, clearance: tuple[str, ...] = ()
) -> BundleRegistry:
    bundle = load_bundle(root)
    service = _service(bundle, bundle_access=bundle_access, clearance=clearance)
    return BundleRegistry([BundleRegistration("b", service)])


class _FailingProvider:
    """An embedding provider that always raises, for index-build-failure tests."""

    name = "failing"
    dimension = 8

    def embed(self, texts: list[str]) -> list[Vector]:
        raise RuntimeError("embedding backend unavailable")


class _BlockingProvider:
    """Blocks inside ``embed`` until released, for deterministic concurrency tests."""

    def __init__(
        self, base: LexicalEmbeddingProvider, started: threading.Event, release: threading.Event
    ) -> None:
        self._base = base
        self._started = started
        self._release = release

    @property
    def name(self) -> str:
        return self._base.name

    @property
    def dimension(self) -> int:
        return self._base.dimension

    def embed(self, texts: list[str]) -> list[Vector]:
        self._started.set()
        assert self._release.wait(timeout=5), "release event was never set"
        return self._base.embed(texts)


def test_no_op_refresh_reports_unchanged_and_records_no_activation_event(
    tmp_path: Path,
) -> None:
    root = tmp_path / "bundle"
    _write_concept(root)
    registry = _registry(root)
    before = registry.active_registration("b")

    outcome = registry.refresh("b")

    assert outcome.changed is False
    assert outcome.revision == before.revision
    assert registry.active_registration("b") is before  # untouched, not merely equal
    assert registry.activation_events() == ()


def test_valid_change_activates_without_restart_and_reads_the_new_content(
    tmp_path: Path,
) -> None:
    root = tmp_path / "bundle"
    _write_concept(root, title="Before")
    registry = _registry(root)
    before = registry.active_registration("b")

    _write_concept(root, title="After")
    outcome = registry.refresh("b")

    assert outcome.changed is True
    assert outcome.health == "current"
    assert outcome.revision != before.revision
    after = registry.active_registration("b")
    assert after is not before
    assert after.revision == outcome.revision
    result = registry.call_tool("b", "read_frontmatter", {"concept_id": CONCEPT_ID})
    assert result["title"] == "After"
    assert result["revision"] == outcome.revision


def test_valid_change_records_exactly_one_body_free_activation_event(tmp_path: Path) -> None:
    root = tmp_path / "bundle"
    _write_concept(root, title="Before")
    registry = _registry(root)

    _write_concept(root, title="Secret Body Marker XYZ123")
    outcome = registry.refresh("b")

    events = registry.activation_events("b")
    assert len(events) == 1
    assert events[0].bundle_id == "b"
    assert events[0].revision == outcome.revision
    assert "Secret Body Marker XYZ123" not in repr(events[0])
    assert "Secret" not in events[0].bundle_id
    assert set(events[0].__dict__) == {"bundle_id", "revision", "activated_at"}


def test_invalid_bundle_keeps_old_revision_active_and_marks_health_failed(
    tmp_path: Path,
) -> None:
    root = tmp_path / "bundle"
    _write_concept(root, title="Good")
    registry = _registry(root)
    before = registry.active_registration("b")

    _write_concept(root, title="Bad", concept_type="")  # empty type -> conformance error
    outcome = registry.refresh("b")

    assert outcome.changed is False
    assert outcome.health == "failed"
    assert outcome.error is not None
    assert outcome.error.stage == "validate"
    assert registry.active_registration("b") is before
    assert registry.health("b") == "failed"
    assert registry.last_error("b") == outcome.error
    assert registry.activation_events() == ()
    result = registry.call_tool("b", "read_frontmatter", {"concept_id": CONCEPT_ID})
    assert result["title"] == "Good"  # still serving the last validated content


def test_a_load_failure_keeps_old_revision_active_and_reports_stage_load(
    tmp_path: Path,
) -> None:
    root = tmp_path / "bundle"
    _write_concept(root, title="Good")
    registry = _registry(root)
    before = registry.active_registration("b")

    (root / "concept.md").write_text("not frontmatter at all\n", encoding="utf-8")
    outcome = registry.refresh("b")

    assert outcome.changed is False
    assert outcome.health == "failed"
    assert outcome.error is not None
    assert outcome.error.stage == "load"
    assert registry.active_registration("b") is before


def test_index_build_failure_keeps_old_bundle_and_index_pair(tmp_path: Path) -> None:
    root = tmp_path / "bundle"
    _write_concept(root, title="Good")
    registry = _registry(root)
    before = registry.active_registration("b")

    _write_concept(root, title="Changed")
    outcome = registry.refresh("b", provider=_FailingProvider())

    assert outcome.changed is False
    assert outcome.health == "failed"
    assert outcome.error is not None
    assert outcome.error.stage == "index"
    assert registry.active_registration("b") is before
    assert registry.active_registration("b").service.index.provider.name != "failing"


def test_concept_id_index_mismatch_is_rejected_as_an_index_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "bundle"
    _write_concept(root, title="Good")
    registry = _registry(root)
    before = registry.active_registration("b")

    def _mismatched_build(bundle: Bundle, provider: object) -> EmbeddingIndex:
        # A real index whose concept id set diverges from the bundle's -- the
        # defensive check this simulates a bug or race producing.
        return EmbeddingIndex(provider, {"not-a-real-concept": [0.0]})  # type: ignore[arg-type]

    monkeypatch.setattr(EmbeddingIndex, "build", staticmethod(_mismatched_build))
    _write_concept(root, title="Changed")
    outcome = registry.refresh("b")

    assert outcome.changed is False
    assert outcome.error is not None
    assert outcome.error.stage == "index"
    assert registry.active_registration("b") is before


def test_refresh_error_message_never_contains_source_or_concept_body_text(
    tmp_path: Path,
) -> None:
    secret = "UNIQUE-SOURCE-MARKER-98765"
    root = tmp_path / "bundle"
    _write_concept(root, title="Good")
    registry = _registry(root)

    # Malformed YAML frontmatter whose body carries the marker -- a naive
    # implementation that echoes str(exc)/file text could leak it.
    (root / "concept.md").write_text(
        f"---\ntype: [unterminated\n---\n{secret}\n", encoding="utf-8"
    )
    outcome = registry.refresh("b")

    assert outcome.error is not None
    assert secret not in outcome.error.message
    assert secret not in outcome.error.stage


def test_concurrent_reads_during_activation_see_only_the_old_or_new_revision(
    tmp_path: Path,
) -> None:
    root = tmp_path / "bundle"
    _write_concept(root, title="Before")
    registry = _registry(root)
    old_revision = registry.active_registration("b").revision
    _write_concept(root, title="After")

    started = threading.Event()
    release = threading.Event()
    provider = _BlockingProvider(LexicalEmbeddingProvider(), started, release)

    mid_build_observations: list[str] = []
    stop = threading.Event()

    def reader() -> None:
        while not stop.is_set():
            mid_build_observations.append(
                str(registry.call_tool("b", "list_index", {})["revision"])
            )

    reader_thread = threading.Thread(target=reader)
    reader_thread.start()

    outcomes: list[object] = []
    refresh_thread = threading.Thread(
        target=lambda: outcomes.append(registry.refresh("b", provider=provider))
    )
    refresh_thread.start()

    assert started.wait(timeout=5), "index build never started"
    snapshot_while_blocked = tuple(mid_build_observations)
    release.set()
    refresh_thread.join(timeout=5)
    stop.set()
    reader_thread.join(timeout=5)

    assert snapshot_while_blocked, "reader thread never observed a revision mid-build"
    assert set(snapshot_while_blocked) == {old_revision}  # never a partial/new revision

    new_revision = registry.active_registration("b").revision
    assert new_revision != old_revision
    assert set(mid_build_observations) <= {old_revision, new_revision}
    assert registry.call_tool("b", "list_index", {})["revision"] == new_revision


def test_access_control_survives_refresh(tmp_path: Path) -> None:
    root = tmp_path / "bundle"
    _write_concept(root, title="Before")
    registry = _registry(root, bundle_access="confidential", clearance=())  # no clearance

    with pytest.raises(AccessDeniedError):
        registry.call_tool("b", "list_index", {})

    _write_concept(root, title="After")
    outcome = registry.refresh("b")
    assert outcome.changed is True

    with pytest.raises(AccessDeniedError):
        registry.call_tool("b", "list_index", {})  # still denied after activation


def test_multi_bundle_refresh_affects_only_the_addressed_bundle(tmp_path: Path) -> None:
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    _write_concept(root_a, title="A before")
    _write_concept(root_b, title="B before")
    bundle_a = load_bundle(root_a)
    bundle_b = load_bundle(root_b)
    registry = BundleRegistry(
        [
            BundleRegistration("a", _service(bundle_a)),
            BundleRegistration("b", _service(bundle_b)),
        ]
    )
    b_before = registry.active_registration("b")

    _write_concept(root_a, title="A after")
    outcome = registry.refresh("a")

    assert outcome.changed is True
    assert registry.active_registration("b") is b_before
    assert registry.activation_events("b") == ()
    assert len(registry.activation_events("a")) == 1
