"""Sandboxed HTTP/SSE boundary: traversal-only, no filesystem exposure (M9 PR-1).

A served client only ever talks to ``GET /bundles``, ``GET /health``,
``GET /activations``, ``POST /refresh/<bundle_id>``, and
``POST /tools/<tool>``. These tests exercise the real ``KoshaHttpServer`` over
a loopback TCP socket (not the handler class in isolation) so they defend
what an actual network client experiences: only a clearance-authorized bundle
is listed, an unauthorized or unknown bundle is denied rather than silently
served, and nothing resembling a file path ever reaches bundle content.
"""

from __future__ import annotations

import json
from http.client import HTTPConnection
from typing import Any

import pytest

from kosha.server.registry import BundleRegistry

StartServer = Any  # the start_server fixture's factory callable
RunningServer = Any


def _get(conn: HTTPConnection, path: str) -> tuple[int, dict[str, str], bytes]:
    conn.request("GET", path)
    response = conn.getresponse()
    body = response.read()
    return response.status, dict(response.getheaders()), body


def _post_json(
    conn: HTTPConnection, path: str, payload: object
) -> tuple[int, dict[str, str], bytes]:
    body = json.dumps(payload).encode("utf-8")
    conn.request("POST", path, body=body, headers={"Content-Type": "application/json"})
    response = conn.getresponse()
    return response.status, dict(response.getheaders()), response.read()


def test_get_bundles_lists_only_the_authorized_bundle(
    registry: BundleRegistry, start_server: StartServer
) -> None:
    server: RunningServer = start_server(registry)
    status, headers, body = _get(server.connection(), "/bundles")

    assert status == 200
    assert "application/json" in headers.get("Content-Type", "")
    assert json.loads(body) == {
        "bundles": [
            {
                "bundle_id": "northwind",
                "revision": registry.active_registration("northwind").revision,
            }
        ]
    }


def test_get_activations_is_a_one_shot_json_endpoint_scoped_to_authorized_bundles(
    registry: BundleRegistry, start_server: StartServer
) -> None:
    server: RunningServer = start_server(registry)
    status, headers, body = _get(server.connection(), "/activations")

    assert status == 200
    assert "application/json" in headers.get("Content-Type", "")
    # Nothing has been refreshed yet -- no activations have occurred.
    assert json.loads(body) == {"activations": []}


def test_post_tools_answers_a_traversal_call_for_the_authorized_bundle(
    registry: BundleRegistry, start_server: StartServer
) -> None:
    server: RunningServer = start_server(registry)
    args = {"query": "how long to return an item", "k": 3}
    status, headers, body = _post_json(
        server.connection(), "/tools/find_concepts", {"bundle_id": "northwind", **args}
    )
    expected = registry.call_tool("northwind", "find_concepts", args)

    assert status == 200
    assert "application/json" in headers.get("Content-Type", "")
    assert json.loads(body) == expected


def test_post_tools_denies_a_bundle_the_service_has_no_clearance_for(
    registry: BundleRegistry, start_server: StartServer
) -> None:
    server: RunningServer = start_server(registry)
    status, _, body = _post_json(server.connection(), "/tools/list_index", {"bundle_id": "good"})

    assert status == 403
    assert json.loads(body)["error"]["code"] == "access_denied"


def test_post_tools_missing_bundle_id_is_a_400(
    registry: BundleRegistry, start_server: StartServer
) -> None:
    server: RunningServer = start_server(registry)
    status, _, body = _post_json(server.connection(), "/tools/list_index", {})

    assert status == 400
    assert json.loads(body)["error"]["code"] == "missing_bundle_id"


def test_post_tools_unknown_bundle_id_is_a_404(
    registry: BundleRegistry, start_server: StartServer
) -> None:
    server: RunningServer = start_server(registry)
    status, _, body = _post_json(
        server.connection(), "/tools/list_index", {"bundle_id": "does-not-exist"}
    )

    assert status == 404
    assert json.loads(body)["error"]["code"] == "not_found"


def test_post_tools_unknown_tool_name_is_a_404(
    registry: BundleRegistry, start_server: StartServer
) -> None:
    server: RunningServer = start_server(registry)
    status, _, body = _post_json(
        server.connection(), "/tools/drop_table", {"bundle_id": "northwind"}
    )

    assert status == 404
    assert json.loads(body)["error"]["code"] == "not_found"


def test_post_tools_missing_required_tool_argument_is_a_400(
    registry: BundleRegistry, start_server: StartServer
) -> None:
    server: RunningServer = start_server(registry)
    status, _, body = _post_json(
        server.connection(), "/tools/find_concepts", {"bundle_id": "northwind"}
    )

    assert status == 400
    assert json.loads(body)["error"]["code"] == "bad_request"


def test_post_tools_malformed_json_body_is_a_400(
    registry: BundleRegistry, start_server: StartServer
) -> None:
    server: RunningServer = start_server(registry)
    conn = server.connection()
    conn.request(
        "POST",
        "/tools/list_index",
        body=b"{not-json",
        headers={"Content-Type": "application/json"},
    )
    response = conn.getresponse()
    status, body = response.status, response.read()

    assert status == 400
    assert json.loads(body)["error"]["code"] == "bad_json"


def test_post_to_a_non_tools_path_is_404_not_a_file_read(
    registry: BundleRegistry, start_server: StartServer
) -> None:
    server: RunningServer = start_server(registry)
    status, _, body = _post_json(
        server.connection(), "/policies/shipping.md", {"bundle_id": "northwind"}
    )

    assert status == 404
    assert b"3-5 business days" not in body


@pytest.mark.parametrize(
    "path",
    [
        "/policies/shipping.md",
        "/bundles/northwind/policies/shipping.md",
        "/index.md",
        "/log.md",
        "/favicon.ico",
        "/../../../../etc/passwd",
    ],
)
def test_filesystem_like_get_paths_return_404_never_file_contents(
    registry: BundleRegistry, start_server: StartServer, path: str
) -> None:
    server: RunningServer = start_server(registry)
    status, _, body = _get(server.connection(), path)

    assert status == 404
    # The real markdown body must never leak through a raw path probe: there
    # is no filesystem-serving route at all, only /bundles, /health,
    # /activations, /refresh/<id>, /tools/*.
    assert b"3-5 business days" not in body


def test_post_tools_an_unexpected_registry_exception_is_a_500(
    registry: BundleRegistry, start_server: StartServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An unanticipated failure inside the registry/service (a bug, not a
    # caller error) must still answer as JSON with a 500, never crash the
    # handler thread or leak a raw traceback to the client.
    def _boom(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("boom")

    monkeypatch.setattr(BundleRegistry, "call_tool", _boom)
    server: RunningServer = start_server(registry)
    status, _, body = _post_json(
        server.connection(), "/tools/list_index", {"bundle_id": "northwind"}
    )

    assert status == 500
    assert json.loads(body) == {
        "error": {
            "code": "server_error",
            "message": "served traversal failed; check server logs",
        }
    }


def test_get_bundles_an_unexpected_registry_exception_is_a_500(
    registry: BundleRegistry, start_server: StartServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Mirrors the POST unexpected-exception case for the GET /bundles listing
    # path: a bug inside authorized_bundle_ids() must still answer as JSON
    # with a 500, never crash the handler thread or leak a raw traceback.
    def _boom(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("boom")

    monkeypatch.setattr(BundleRegistry, "authorized_bundle_ids", _boom)
    server: RunningServer = start_server(registry)
    status, _, body = _get(server.connection(), "/bundles")

    assert status == 500
    assert json.loads(body) == {
        "error": {
            "code": "server_error",
            "message": "served traversal failed; check server logs",
        }
    }


def test_post_tools_a_non_json_serializable_result_is_a_500(
    registry: BundleRegistry, start_server: StartServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A tool result json.dumps cannot encode (a bug, not a caller error) must
    # still fail closed as a JSON 500. _send_json builds the payload before
    # calling send_response(), so a serialization TypeError here must never
    # leave a half-started response the client hangs reading.
    def _unserializable(*_args: object, **_kwargs: object) -> object:
        return {"result": object()}

    monkeypatch.setattr(BundleRegistry, "call_tool", _unserializable)
    server: RunningServer = start_server(registry)
    status, _, body = _post_json(
        server.connection(), "/tools/list_index", {"bundle_id": "northwind"}
    )

    assert status == 500
    assert json.loads(body) == {
        "error": {
            "code": "server_error",
            "message": "served traversal failed; check server logs",
        }
    }
