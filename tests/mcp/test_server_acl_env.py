"""Tests that the shipped kosha-mcp entry point wires bundle ACL from the env.

Prior to this, ``main()`` never passed ``bundle_access``/``clearance`` to
``KoshaKnowledgeService``, so the shipped binary served every bundle openly
regardless of the ACL support the service layer already had (tests/mcp/
test_acl.py). ``main()`` itself blocks on stdio, so these tests exercise the
pure env-parsing helpers it delegates to.
"""

from __future__ import annotations

import asyncio

from mcp.shared.memory import create_connected_server_and_client_session as connect

from kosha.index.embedding import EmbeddingIndex
from kosha.mcp.server import build_server, resolve_bundle_access, resolve_clearance
from kosha.mcp.service import KoshaKnowledgeService
from kosha.model import Bundle
from kosha.providers import LexicalEmbeddingProvider


def test_resolve_bundle_access_defaults_to_open() -> None:
    assert resolve_bundle_access({}) is None


def test_resolve_bundle_access_reads_the_configured_label() -> None:
    assert resolve_bundle_access({"KOSHA_BUNDLE_ACCESS": "confidential"}) == "confidential"


def test_resolve_bundle_access_treats_blank_as_unset() -> None:
    assert resolve_bundle_access({"KOSHA_BUNDLE_ACCESS": "  "}) is None


def test_resolve_clearance_defaults_to_empty() -> None:
    assert resolve_clearance({}) == frozenset()


def test_resolve_clearance_splits_comma_separated_labels() -> None:
    env = {"KOSHA_CLEARANCE": "support-team, confidential ,ops"}
    assert resolve_clearance(env) == frozenset({"support-team", "confidential", "ops"})


def test_resolve_clearance_ignores_empty_segments() -> None:
    assert resolve_clearance({"KOSHA_CLEARANCE": "a,,b,"}) == frozenset({"a", "b"})


def test_bundle_access_set_without_clearance_denies_by_default() -> None:
    # Fail-closed: configuring an access label without any clearance must not
    # silently fall back to an open bundle.
    assert resolve_bundle_access({"KOSHA_BUNDLE_ACCESS": "confidential"}) == "confidential"
    assert resolve_clearance({"KOSHA_BUNDLE_ACCESS": "confidential"}) == frozenset()


def _service_from_env(env: dict[str, str], northwind: Bundle) -> KoshaKnowledgeService:
    """Build a service the way ``main()`` does, from parsed env variables."""
    index = EmbeddingIndex.build(northwind, LexicalEmbeddingProvider())
    return KoshaKnowledgeService(
        northwind,
        index,
        bundle_access=resolve_bundle_access(env),
        clearance=resolve_clearance(env),
    )


def test_env_wired_service_denies_an_uncleared_caller_over_mcp(northwind: Bundle) -> None:
    service = _service_from_env({"KOSHA_BUNDLE_ACCESS": "confidential"}, northwind)
    server = build_server(service)

    async def run() -> bool:
        async with connect(server) as client:
            result = await client.call_tool("list_index", {})
            return result.isError

    assert asyncio.run(run()) is True


def test_env_wired_service_serves_a_cleared_caller_over_mcp(northwind: Bundle) -> None:
    env = {"KOSHA_BUNDLE_ACCESS": "confidential", "KOSHA_CLEARANCE": "confidential"}
    service = _service_from_env(env, northwind)
    server = build_server(service)

    async def run() -> bool:
        async with connect(server) as client:
            result = await client.call_tool("list_index", {})
            return result.isError

    assert asyncio.run(run()) is False
