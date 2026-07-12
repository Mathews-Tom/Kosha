"""Resource subscriptions and post-activation update notifications (M9).

:class:`ResourceSubscriptionRegistry` tracks, per resource URI, which live
MCP sessions asked for ``notifications/resources/updated`` -- and delivers
them strictly after a successful, already-atomic
:meth:`~kosha.server.registry.BundleRegistry.refresh` activation, never
before it and never for a no-op or failed attempt (source spec §16: "a
bundle activation may notify the bundle resource and affected resource
templates without sending bodies"). :func:`refresh_and_notify` is the single
integration point that composes the two: callers (production watch-mode
wiring, or a test driving activation directly) never call
``registry.refresh`` and notify separately, so the "notify only after
successful activation" ordering cannot be gotten wrong at a call site.

This server process serves one fixed clearance for its whole lifetime (see
``kosha.mcp.server.resolve_clearance``: read once from the environment at
startup, not per connection), so a subscriber's eligibility for a bundle's
notifications is exactly :func:`kosha.mcp.resources.require_authorized_bundle`
-- the same bundle-level ACL gate resource reads use. A caller can only
subscribe to a bundle-scoped URI it is currently authorized to read, and
:meth:`ResourceSubscriptionRegistry.notify_activation` only ever considers
resources scoped to the bundle that actually activated (or the bundle list,
whose content is itself already ACL-filtered), so an unrelated bundle's
subscriber is never notified and never learns a bundle it cannot see exists
or changed.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.lowlevel.server import NotificationOptions
from mcp.server.session import ServerSession
from mcp.types import ServerCapabilities
from pydantic import AnyUrl

from kosha.mcp.resources import BundlesListRef, parse_resource_uri, require_authorized_bundle
from kosha.providers.base import EmbeddingProvider
from kosha.server.registry import BundleRegistry
from kosha.server.revision import RefreshOutcome


class ResourceSubscriptionRegistry:
    """Tracks per-session ``kosha://`` resource subscriptions and delivers updates."""

    def __init__(self) -> None:
        self._subscribers: dict[str, set[ServerSession]] = {}

    def subscribe(self, uri: str, session: ServerSession) -> None:
        """Record ``session``'s subscription to ``uri`` (idempotent)."""

        self._subscribers.setdefault(uri, set()).add(session)

    def unsubscribe(self, uri: str, session: ServerSession) -> None:
        """Drop ``session``'s subscription to ``uri``, if present (idempotent)."""

        sessions = self._subscribers.get(uri)
        if sessions is None:
            return
        sessions.discard(session)
        if not sessions:
            del self._subscribers[uri]

    def discard_session(self, session: ServerSession) -> None:
        """Drop ``session`` from every subscription (e.g. on disconnect)."""

        for uri in list(self._subscribers):
            self.unsubscribe(uri, session)

    def subscriber_count(self, uri: str) -> int:
        """Return how many sessions currently subscribe to ``uri``."""

        return len(self._subscribers.get(uri, ()))

    async def notify_activation(self, bundle_id: str) -> None:
        """Deliver ``notifications/resources/updated`` for one activated bundle.

        Only URIs scoped to ``bundle_id`` (its detail, index, and concept
        resources) plus the bundle list are considered; every other
        subscription is left untouched. A session whose delivery fails (a
        closed/broken transport) is skipped without blocking delivery to any
        other subscriber of the same or another relevant resource.
        """

        for uri, sessions in list(self._subscribers.items()):
            if not sessions or not _is_relevant(uri, bundle_id):
                continue
            parsed_uri = AnyUrl(uri)
            for session in tuple(sessions):
                try:
                    await session.send_resource_updated(parsed_uri)
                except Exception:  # one broken subscriber must never
                    # block delivery to the rest; matches BundleWatcher.poll_once's
                    # per-bundle isolation, applied here per-subscriber instead.
                    continue


def _is_relevant(uri: str, bundle_id: str) -> bool:
    try:
        ref = parse_resource_uri(uri)
    except ValueError:
        return False
    if isinstance(ref, BundlesListRef):
        return True
    return ref.bundle_id == bundle_id


async def refresh_and_notify(
    registry: BundleRegistry,
    subscriptions: ResourceSubscriptionRegistry,
    bundle_id: str,
    *,
    provider: EmbeddingProvider | None = None,
    clock: Callable[[], datetime] | None = None,
) -> RefreshOutcome:
    """Refresh one bundle and, only on a successful activation, notify subscribers.

    A no-op (unchanged on-disk content) or a failed refresh -- either
    already reported by ``registry.refresh`` without touching the active
    registration -- notifies nobody, so a subscriber never observes a
    notification that outruns activation or reports a change that never
    actually landed.
    """

    outcome = registry.refresh(bundle_id, provider=provider, clock=clock)
    if outcome.changed:
        await subscriptions.notify_activation(bundle_id)
    return outcome


def authorize_subscription(registry: BundleRegistry, uri: str) -> None:
    """Validate a subscription request's URI and bundle-level ACL.

    Raises :class:`~kosha.mcp.resources.MalformedResourceUriError` for an
    unrecognized URI shape and
    :class:`~kosha.mcp.resources.ResourceAccessError` for an unknown or
    unauthorized bundle -- the same ACL-before-existence gate resource reads
    use, so a caller cannot subscribe its way to an existence oracle for a
    bundle it cannot read.
    """

    ref = parse_resource_uri(uri)
    if isinstance(ref, BundlesListRef):
        return
    require_authorized_bundle(registry, ref.bundle_id)


def wire_subscriptions(server: FastMCP, registry: BundleRegistry) -> ResourceSubscriptionRegistry:
    """Register subscribe/unsubscribe handlers on ``server`` and advertise the capability.

    Returns the new :class:`ResourceSubscriptionRegistry` so the caller can
    drive :func:`refresh_and_notify` against the exact instance backing this
    server's sessions.
    """

    subscriptions = ResourceSubscriptionRegistry()
    mcp_server = server._mcp_server  # no public accessor exists;
    # mirrors mcp.shared.memory.create_connected_server_and_client_session's own
    # ``server._mcp_server`` access for the same reason (see its TODO comment).

    @mcp_server.subscribe_resource()  # type: ignore[no-untyped-call,untyped-decorator]
    async def _subscribe(uri: AnyUrl) -> None:
        authorize_subscription(registry, str(uri))
        session = mcp_server.request_context.session
        subscriptions.subscribe(str(uri), session)

    @mcp_server.unsubscribe_resource()  # type: ignore[no-untyped-call,untyped-decorator]
    async def _unsubscribe(uri: AnyUrl) -> None:
        session = mcp_server.request_context.session
        subscriptions.unsubscribe(str(uri), session)

    _advertise_resource_subscriptions(server)
    return subscriptions


def _advertise_resource_subscriptions(server: FastMCP) -> None:
    """Report ``resources.subscribe: true`` in this server's capability negotiation.

    mcp==1.28.1's ``Server.get_capabilities`` hardcodes
    ``ResourcesCapability(subscribe=False, ...)`` whenever a
    ``ListResourcesRequest`` handler is registered -- it never checks whether
    ``SubscribeRequest``/``UnsubscribeRequest`` handlers are also registered,
    and the SDK exposes no public option to change this (verified against
    the installed SDK: ``Server.get_capabilities`` takes no subscribe flag).
    This server genuinely implements resource subscriptions (see
    ``wire_subscriptions`` above), so wrap the bound method on this one
    server instance to advertise the capability that matches its actual
    behavior, without patching the installed library.
    """

    mcp_server = server._mcp_server  # see wire_subscriptions.
    original_get_capabilities = mcp_server.get_capabilities

    def get_capabilities(
        notification_options: NotificationOptions,
        experimental_capabilities: dict[str, dict[str, Any]],
    ) -> ServerCapabilities:
        capabilities = original_get_capabilities(notification_options, experimental_capabilities)
        if capabilities.resources is not None:
            capabilities.resources.subscribe = True
        return capabilities

    mcp_server.get_capabilities = get_capabilities  # type: ignore[method-assign]
