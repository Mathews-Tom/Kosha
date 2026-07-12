"""Versioned ``kosha://`` bundle resources (M9): URIs, ACL, MIME, temporal parity.

Covers both layers: the pure URI/ACL helpers in :mod:`kosha.mcp.resources`
(no protocol involved) and the real protocol surface (``resources/list``,
``resources/templates/list``, ``resources/read``) over an in-memory MCP
client, mirroring tests/mcp/test_registry_server.py's protocol-level style.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

import pytest
from mcp.shared.exceptions import McpError
from mcp.shared.memory import create_connected_server_and_client_session as connect

from kosha.mcp.resources import (
    BundleRef,
    BundlesListRef,
    ConceptRef,
    IndexRef,
    MalformedResourceUriError,
    ResourceAccessError,
    bundle_uri,
    bundles_list_uri,
    concept_uri,
    decode_segment,
    encode_segment,
    index_uri,
    parse_resource_uri,
    require_authorized_bundle,
)
from kosha.mcp.server import build_server
from kosha.mcp.service import KoshaKnowledgeService
from kosha.model import Bundle
from kosha.server.registry import BundleRegistration, BundleRegistry

ServiceFactory = Callable[..., KoshaKnowledgeService]


@pytest.fixture
def registry(
    build_service: ServiceFactory, northwind: Bundle, good_bundle: Bundle
) -> BundleRegistry:
    return BundleRegistry(
        [
            BundleRegistration("northwind", build_service(northwind)),
            BundleRegistration("good", build_service(good_bundle)),
            BundleRegistration(
                "locked", build_service(northwind, bundle_access="confidential")
            ),
        ]
    )


# --- pure URI helpers --------------------------------------------------------


def test_segment_round_trips_through_encode_decode() -> None:
    for raw in ("simple", "with/slash", "with space", "with?query#frag", "unicode-résumé"):
        assert decode_segment(encode_segment(raw)) == raw


def test_encode_segment_rejects_empty() -> None:
    with pytest.raises(ValueError):
        encode_segment("")


def test_decode_segment_rejects_empty() -> None:
    with pytest.raises(MalformedResourceUriError):
        decode_segment("")


@pytest.mark.parametrize(
    "uri,expected",
    [
        (bundles_list_uri(), BundlesListRef()),
        (bundle_uri("northwind"), BundleRef(bundle_id="northwind")),
        (
            index_uri("northwind", "policies/returns"),
            IndexRef(bundle_id="northwind", scope="policies/returns"),
        ),
        (
            concept_uri("northwind", "policies/returns/gold-members"),
            ConceptRef(bundle_id="northwind", concept_id="policies/returns/gold-members"),
        ),
    ],
)
def test_parse_resource_uri_round_trips_every_shape(uri: str, expected: object) -> None:
    assert parse_resource_uri(uri) == expected


@pytest.mark.parametrize(
    "uri",
    [
        "http://bundles",
        "kosha://",
        "kosha://other",
        "kosha://bundles/",
        "kosha://bundles/x/index",
        "kosha://bundles/x/wrong/scope",
        "kosha://bundles/x/index/scope/extra",
    ],
)
def test_parse_resource_uri_rejects_unrecognized_shapes(uri: str) -> None:
    with pytest.raises(MalformedResourceUriError):
        parse_resource_uri(uri)


def test_require_authorized_bundle_gives_identical_error_for_unknown_and_forbidden(
    registry: BundleRegistry,
) -> None:
    with pytest.raises(ResourceAccessError) as unknown_exc:
        require_authorized_bundle(registry, "does-not-exist")
    with pytest.raises(ResourceAccessError) as forbidden_exc:
        require_authorized_bundle(registry, "locked")
    # Same exception type, same message: a caller cannot distinguish
    # "no such bundle" from "bundle exists, access denied".
    assert str(unknown_exc.value) == str(forbidden_exc.value)


def test_require_authorized_bundle_allows_an_authorized_bundle(
    registry: BundleRegistry,
) -> None:
    require_authorized_bundle(registry, "northwind")  # does not raise


# --- protocol-level surface ---------------------------------------------------


async def _read_json(client: Any, uri: str) -> tuple[dict[str, Any], str | None]:
    result = await client.read_resource(uri)
    content = result.contents[0]
    return json.loads(content.text), content.mimeType


def test_resource_capabilities_list_every_uri_and_template(registry: BundleRegistry) -> None:
    server = build_server(registry)

    async def run() -> tuple[list[Any], list[Any]]:
        async with connect(server) as client:
            resources = await client.list_resources()
            templates = await client.list_resource_templates()
            return resources.resources, templates.resourceTemplates

    resources, templates = asyncio.run(run())
    assert {r.uri.unicode_string() for r in resources} == {"kosha://bundles"}
    assert all(r.mimeType == "application/json" for r in resources)
    assert {t.uriTemplate for t in templates} == {
        "kosha://bundles/{bundle_id}",
        "kosha://bundles/{bundle_id}/index/{scope}",
        "kosha://bundles/{bundle_id}/concepts/{concept_id}",
    }
    assert all(t.mimeType == "application/json" for t in templates)


def test_bundles_list_resource_matches_the_list_bundles_tool(registry: BundleRegistry) -> None:
    server = build_server(registry)

    async def run() -> tuple[dict[str, Any], Any]:
        async with connect(server) as client:
            body, _mime = await _read_json(client, "kosha://bundles")
            tool_result = await client.call_tool("list_bundles", {})
            return body, tool_result.structuredContent

    body, tool_body = asyncio.run(run())
    assert body == tool_body
    ids = {entry["bundle_id"] for entry in body["bundles"]}
    assert ids == {"northwind", "good"}  # "locked" is never disclosed


def test_bundle_resource_reports_the_active_revision(registry: BundleRegistry) -> None:
    server = build_server(registry)
    expected_revision = registry.active_registration("northwind").revision

    async def run() -> dict[str, Any]:
        async with connect(server) as client:
            body, mime = await _read_json(client, bundle_uri("northwind"))
            assert mime == "application/json"
            return body

    body = asyncio.run(run())
    assert body == {"bundle_id": "northwind", "revision": expected_revision}


def test_index_resource_matches_the_list_index_tool(registry: BundleRegistry) -> None:
    server = build_server(registry)

    async def run() -> tuple[dict[str, Any], Any]:
        async with connect(server) as client:
            body, _mime = await _read_json(client, index_uri("northwind", "policies/returns"))
            tool_result = await client.call_tool(
                "list_index", {"bundle_id": "northwind", "scope": "policies/returns"}
            )
            return body, tool_result.structuredContent

    body, tool_body = asyncio.run(run())
    assert body == tool_body
    targets = {
        entry["target"] for section in body["sections"] for entry in section["entries"]
    }
    assert "policies/returns/gold-members" in targets


def test_concept_resource_matches_load_concept_with_no_asof(registry: BundleRegistry) -> None:
    server = build_server(registry)
    concept_id = "concepts/customer-lifetime-value"

    async def run() -> tuple[dict[str, Any], Any]:
        async with connect(server) as client:
            body, _mime = await _read_json(client, concept_uri("good", concept_id))
            tool_result = await client.call_tool(
                "load_concept", {"bundle_id": "good", "concept_id": concept_id}
            )
            return body, tool_result.structuredContent

    body, tool_body = asyncio.run(run())
    assert body == tool_body
    assert body["concept_id"] == concept_id


def test_concept_resource_hides_expired_claims_like_the_tool(
    temporal_service: KoshaKnowledgeService,
) -> None:
    gold_concept_id = "policies/returns/gold-members"
    registry = BundleRegistry([BundleRegistration("northwind", temporal_service)])
    server = build_server(registry)

    async def run() -> dict[str, Any]:
        async with connect(server) as client:
            body, _mime = await _read_json(
                client, concept_uri("northwind", gold_concept_id)
            )
            return body

    body = asyncio.run(run())
    assert "45 days" in body["body"]
    assert "60 days" not in body["body"]


def test_reading_a_locked_bundle_resource_is_denied_over_mcp(registry: BundleRegistry) -> None:
    server = build_server(registry)

    async def run() -> None:
        async with connect(server) as client:
            with pytest.raises(McpError):
                await client.read_resource(bundle_uri("locked"))

    asyncio.run(run())


def test_locked_and_unknown_bundle_resources_fail_with_the_same_message(
    registry: BundleRegistry,
) -> None:
    server = build_server(registry)

    async def run() -> tuple[str, str]:
        async with connect(server) as client:
            with pytest.raises(McpError) as locked_exc:
                await client.read_resource(bundle_uri("locked"))
            with pytest.raises(McpError) as unknown_exc:
                await client.read_resource(bundle_uri("does-not-exist"))
            return locked_exc.value.error.message, unknown_exc.value.error.message

    locked_message, unknown_message = asyncio.run(run())
    assert locked_message == unknown_message


def test_index_and_concept_resources_are_also_denied_for_a_locked_bundle(
    registry: BundleRegistry,
) -> None:
    server = build_server(registry)

    async def run() -> None:
        async with connect(server) as client:
            with pytest.raises(McpError):
                await client.read_resource(index_uri("locked", "policies"))
            with pytest.raises(McpError):
                await client.read_resource(
                    concept_uri("locked", "policies/returns/gold-members")
                )

    asyncio.run(run())


def test_malformed_resource_uri_fails_distinctly_from_access_denied(
    registry: BundleRegistry,
) -> None:
    server = build_server(registry)

    async def run() -> tuple[str, str]:
        async with connect(server) as client:
            with pytest.raises(McpError) as malformed_exc:
                await client.read_resource("kosha://bundles/x/wrong-shape")
            with pytest.raises(McpError) as denied_exc:
                await client.read_resource(bundle_uri("locked"))
            return malformed_exc.value.error.message, denied_exc.value.error.message

    malformed_message, denied_message = asyncio.run(run())
    assert malformed_message != denied_message
    assert "access denied" in denied_message


def test_a_scope_containing_a_slash_round_trips_through_the_resource_uri(
    registry: BundleRegistry,
) -> None:
    server = build_server(registry)

    async def run() -> dict[str, Any]:
        async with connect(server) as client:
            body, _mime = await _read_json(
                client, index_uri("northwind", "policies/returns")
            )
            return body

    body = asyncio.run(run())
    assert body["scope"] == "policies/returns"
