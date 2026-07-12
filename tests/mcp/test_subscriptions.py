"""Resource subscriptions and post-activation notifications (M9).

Covers the unit-level :class:`~kosha.mcp.subscriptions.ResourceSubscriptionRegistry`
and the full protocol round trip: a real MCP client subscribes, a bundle is
refreshed through :func:`~kosha.mcp.subscriptions.refresh_and_notify`, and the
client observes ``notifications/resources/updated`` -- but only when, and
only for whom, the source spec requires.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import mcp.types as types
import pytest
from mcp.shared.exceptions import McpError
from mcp.shared.memory import create_connected_server_and_client_session as connect
from pydantic import AnyUrl

from kosha.index.embedding import EmbeddingIndex
from kosha.mcp.resources import bundle_uri, bundles_list_uri
from kosha.mcp.server import build_registry_server_with_subscriptions
from kosha.mcp.service import KoshaKnowledgeService
from kosha.mcp.subscriptions import ResourceSubscriptionRegistry, refresh_and_notify
from kosha.model import Bundle
from kosha.okf.load import load_bundle
from kosha.providers import LexicalEmbeddingProvider
from kosha.server.registry import BundleRegistration, BundleRegistry

CONCEPT_ID = "concept"


def _write_concept(root: Path, *, title: str = "Example", concept_type: str = "policy") -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "concept.md").write_text(
        f'---\ntype: "{concept_type}"\ntitle: {title}\n---\nBody text.\n', encoding="utf-8"
    )


def _service(bundle: Bundle) -> KoshaKnowledgeService:
    index = EmbeddingIndex.build(bundle, LexicalEmbeddingProvider())
    return KoshaKnowledgeService(bundle, index)


def _registry(*bundle_ids_and_roots: tuple[str, Path]) -> BundleRegistry:
    registrations = [
        BundleRegistration(bundle_id, _service(load_bundle(root)))
        for bundle_id, root in bundle_ids_and_roots
    ]
    return BundleRegistry(registrations)


# --- unit-level registry ------------------------------------------------------


class _FakeSession:
    """A minimal stand-in exposing only what the registry calls."""

    def __init__(self) -> None:
        self.updates: list[AnyUrl] = []
        self.fail = False

    async def send_resource_updated(self, uri: AnyUrl) -> None:
        if self.fail:
            raise RuntimeError("session gone")
        self.updates.append(uri)


def test_notify_activation_reaches_only_relevant_subscribers() -> None:
    async def run() -> None:
        registry = ResourceSubscriptionRegistry()
        bundle_session = _FakeSession()
        other_session = _FakeSession()
        list_session = _FakeSession()
        registry.subscribe(bundle_uri("a"), bundle_session)
        registry.subscribe(bundle_uri("b"), other_session)
        registry.subscribe(bundles_list_uri(), list_session)

        await registry.notify_activation("a")

        assert [str(u) for u in bundle_session.updates] == [bundle_uri("a")]
        assert other_session.updates == []  # a different bundle: never notified
        assert [str(u) for u in list_session.updates] == [bundles_list_uri()]

    asyncio.run(run())


def test_unsubscribe_stops_further_notifications() -> None:
    async def run() -> None:
        registry = ResourceSubscriptionRegistry()
        session = _FakeSession()
        registry.subscribe(bundle_uri("a"), session)
        registry.unsubscribe(bundle_uri("a"), session)

        await registry.notify_activation("a")

        assert session.updates == []
        assert registry.subscriber_count(bundle_uri("a")) == 0

    asyncio.run(run())


def test_a_broken_subscriber_never_blocks_delivery_to_another() -> None:
    async def run() -> None:
        registry = ResourceSubscriptionRegistry()
        broken = _FakeSession()
        broken.fail = True
        healthy = _FakeSession()
        registry.subscribe(bundle_uri("a"), broken)
        registry.subscribe(bundle_uri("a"), healthy)

        await registry.notify_activation("a")  # must not raise

        assert [str(u) for u in healthy.updates] == [bundle_uri("a")]

    asyncio.run(run())


def test_discard_session_removes_every_subscription() -> None:
    async def run() -> None:
        registry = ResourceSubscriptionRegistry()
        session = _FakeSession()
        registry.subscribe(bundle_uri("a"), session)
        registry.subscribe(bundles_list_uri(), session)
        registry.discard_session(session)

        await registry.notify_activation("a")

        assert session.updates == []

    asyncio.run(run())


# --- refresh_and_notify composition -------------------------------------------


def test_a_no_op_refresh_notifies_nobody(tmp_path: Path) -> None:
    root = tmp_path / "bundle"
    _write_concept(root)
    registry = _registry(("b", root))
    subscriptions = ResourceSubscriptionRegistry()
    session = _FakeSession()
    subscriptions.subscribe(bundle_uri("b"), session)

    outcome = asyncio.run(refresh_and_notify(registry, subscriptions, "b"))

    assert outcome.changed is False
    assert session.updates == []


def test_a_failed_refresh_notifies_nobody(tmp_path: Path) -> None:
    root = tmp_path / "bundle"
    _write_concept(root, title="Good")
    registry = _registry(("b", root))
    subscriptions = ResourceSubscriptionRegistry()
    session = _FakeSession()
    subscriptions.subscribe(bundle_uri("b"), session)

    _write_concept(root, title="Bad", concept_type="")  # empty type -> conformance error
    outcome = asyncio.run(refresh_and_notify(registry, subscriptions, "b"))

    assert outcome.changed is False
    assert outcome.health == "failed"
    assert session.updates == []


def test_a_successful_refresh_notifies_strictly_after_activation(tmp_path: Path) -> None:
    root = tmp_path / "bundle"
    _write_concept(root, title="Before")
    registry = _registry(("b", root))
    subscriptions = ResourceSubscriptionRegistry()
    session = _FakeSession()
    subscriptions.subscribe(bundle_uri("b"), session)

    _write_concept(root, title="After")
    outcome = asyncio.run(refresh_and_notify(registry, subscriptions, "b"))

    assert outcome.changed is True
    assert [str(u) for u in session.updates] == [bundle_uri("b")]
    # The activation the notification announces has already landed.
    assert registry.active_registration("b").revision == outcome.revision


# --- full protocol round trip --------------------------------------------------


def test_server_advertises_the_subscribe_capability(tmp_path: Path) -> None:
    root = tmp_path / "bundle"
    _write_concept(root)
    registry = _registry(("b", root))
    server, _subscriptions = build_registry_server_with_subscriptions(registry)

    async def run() -> types.ServerCapabilities | None:
        async with connect(server) as client:
            return client.get_server_capabilities()

    capabilities = asyncio.run(run())
    assert capabilities is not None
    assert capabilities.resources is not None
    assert capabilities.resources.subscribe is True


def test_client_subscribes_and_receives_an_update_after_refresh(tmp_path: Path) -> None:
    root = tmp_path / "bundle"
    _write_concept(root, title="Before")
    registry = _registry(("b", root))
    server, subscriptions = build_registry_server_with_subscriptions(registry)
    received: list[types.ServerNotification] = []

    async def message_handler(message: object) -> None:
        if isinstance(message, types.ServerNotification):
            received.append(message)

    async def run() -> None:
        async with connect(server, message_handler=message_handler) as client:
            await client.subscribe_resource(AnyUrl(bundle_uri("b")))
            _write_concept(root, title="After")
            outcome = await refresh_and_notify(registry, subscriptions, "b")
            assert outcome.changed is True
            # Give the notification a chance to arrive over the in-memory transport.
            for _ in range(10):
                if received:
                    break
                await asyncio.sleep(0)

    asyncio.run(run())

    updated = [
        msg.root
        for msg in received
        if isinstance(msg.root, types.ResourceUpdatedNotification)
    ]
    assert len(updated) == 1
    assert updated[0].params.uri.unicode_string() == bundle_uri("b")


def test_unsubscribed_bundle_receives_no_notification(tmp_path: Path) -> None:
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    _write_concept(root_a, title="Before")
    _write_concept(root_b, title="Before")
    registry = _registry(("a", root_a), ("b", root_b))
    server, subscriptions = build_registry_server_with_subscriptions(registry)
    received: list[types.ServerNotification] = []

    async def message_handler(message: object) -> None:
        if isinstance(message, types.ServerNotification):
            received.append(message)

    async def run() -> None:
        async with connect(server, message_handler=message_handler) as client:
            await client.subscribe_resource(AnyUrl(bundle_uri("a")))
            _write_concept(root_b, title="After")  # "b" changes, not "a"
            outcome = await refresh_and_notify(registry, subscriptions, "b")
            assert outcome.changed is True
            for _ in range(10):
                await asyncio.sleep(0)

    asyncio.run(run())

    updated = [msg for msg in received if isinstance(msg.root, types.ResourceUpdatedNotification)]
    assert updated == []


def test_subscribing_to_a_locked_bundle_is_denied_over_mcp(tmp_path: Path) -> None:
    root = tmp_path / "bundle"
    _write_concept(root)
    bundle = load_bundle(root)
    index = EmbeddingIndex.build(bundle, LexicalEmbeddingProvider())
    locked = KoshaKnowledgeService(bundle, index, bundle_access="confidential")
    registry = BundleRegistry([BundleRegistration("locked", locked)])
    server, _subscriptions = build_registry_server_with_subscriptions(registry)

    async def run() -> None:
        async with connect(server) as client:
            with pytest.raises(McpError):
                await client.subscribe_resource(AnyUrl(bundle_uri("locked")))

    asyncio.run(run())


def test_subscribing_to_a_malformed_uri_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "bundle"
    _write_concept(root)
    registry = _registry(("b", root))
    server, _subscriptions = build_registry_server_with_subscriptions(registry)

    async def run() -> None:
        async with connect(server) as client:
            with pytest.raises(McpError):
                await client.subscribe_resource(AnyUrl("kosha://not-a-real-shape"))

    asyncio.run(run())
