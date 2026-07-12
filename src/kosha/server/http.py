"""Stdlib HTTP/SSE boundary over traversal-only bundle registries."""

from __future__ import annotations

import json
import logging
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, ClassVar, TypedDict, cast
from urllib.parse import urlparse

from kosha.mcp.service import AccessDeniedError
from kosha.server.registry import BundleRegistry, ToolArguments

JsonObject = dict[str, object]
_LOGGER = logging.getLogger(__name__)



class ErrorBody(TypedDict):
    """Structured error body returned by the served API."""

    error: JsonObject


class KoshaHttpServer(ThreadingHTTPServer):
    """HTTP server carrying the registry its handlers dispatch through."""

    registry: BundleRegistry


class KoshaHttpHandler(BaseHTTPRequestHandler):
    """Expose only traversal calls and bundle discovery over HTTP/SSE."""

    server: KoshaHttpServer
    protocol_version = "HTTP/1.1"
    _TOOL_PREFIX: ClassVar[str] = "/tools/"

    def do_GET(self) -> None:
        try:
            self._handle_get()
        except Exception:
            _LOGGER.exception("served traversal failed for GET %s", urlparse(self.path).path)
            self._send_server_error()

    def do_POST(self) -> None:
        try:
            self._handle_post()
        except Exception:
            _LOGGER.exception("served traversal failed for POST %s", urlparse(self.path).path)
            self._send_server_error()

    def _handle_get(self) -> None:
        path = urlparse(self.path).path
        if path == "/bundles":
            self._send_json(
                HTTPStatus.OK,
                {"bundles": self.server.registry.authorized_bundle_revisions()},
            )
            return
        if path == "/events":
            self._send_sse("ready", {"bundles": self.server.registry.authorized_bundle_ids()})
            return
        self._send_error(HTTPStatus.NOT_FOUND, "not_found", "endpoint not found")

    def _handle_post(self) -> None:
        path = urlparse(self.path).path
        if not path.startswith(self._TOOL_PREFIX):
            self._send_error(HTTPStatus.NOT_FOUND, "not_found", "endpoint not found")
            return
        tool_name = path.removeprefix(self._TOOL_PREFIX)
        if not tool_name or "/" in tool_name:
            self._send_error(HTTPStatus.NOT_FOUND, "not_found", "unknown traversal tool")
            return
        body = self._read_json_body()
        if body is None:
            return
        raw_bundle_id = body.pop("bundle_id", None)
        if not isinstance(raw_bundle_id, str) or not raw_bundle_id:
            self._send_error(
                HTTPStatus.BAD_REQUEST,
                "missing_bundle_id",
                "bundle_id is required",
            )
            return
        try:
            result = self.server.registry.call_tool(
                raw_bundle_id,
                tool_name,
                cast(ToolArguments, body),
            )
        except AccessDeniedError as exc:
            self._send_error(HTTPStatus.FORBIDDEN, "access_denied", str(exc))
        except KeyError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, "not_found", str(exc))
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, "bad_request", str(exc))
        else:
            self._send_json(HTTPStatus.OK, dict(result))

    def log_message(self, format: str, *args: Any) -> None:
        """Silence default stderr logging; callers can wrap the server if needed."""

        return None

    def _read_json_body(self) -> JsonObject | None:
        content_length = self.headers.get("Content-Length")
        if content_length is None:
            self._send_error(HTTPStatus.BAD_REQUEST, "bad_request", "Content-Length is required")
            return None
        try:
            length = int(content_length)
        except ValueError:
            self._send_error(HTTPStatus.BAD_REQUEST, "bad_request", "invalid Content-Length")
            return None
        raw = self.rfile.read(length)
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_error(
                HTTPStatus.BAD_REQUEST,
                "bad_json",
                "request body must be a JSON object",
            )
            return None
        if not isinstance(decoded, dict):
            self._send_error(
                HTTPStatus.BAD_REQUEST,
                "bad_json",
                "request body must be a JSON object",
            )
            return None
        return cast(JsonObject, decoded)

    def _send_sse(self, event: str, data: JsonObject) -> None:
        payload = f"event: {event}\ndata: {json.dumps(data, sort_keys=True)}\n\n".encode()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_json(self, status: HTTPStatus, body: JsonObject | ErrorBody) -> None:
        payload = json.dumps(body, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_error(self, status: HTTPStatus, code: str, message: str) -> None:
        self._send_json(status, {"error": {"code": code, "message": message}})

    def _send_server_error(self) -> None:
        self._send_error(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            "server_error",
            "served traversal failed; check server logs",
        )


def make_http_server(host: str, port: int, registry: BundleRegistry) -> KoshaHttpServer:
    """Create a traversal-only HTTP server without starting its serve loop."""

    server = KoshaHttpServer((host, port), KoshaHttpHandler)
    server.registry = registry
    return server


def serve_forever(host: str, port: int, registry: BundleRegistry) -> None:
    """Run the served traversal boundary until interrupted."""

    with make_http_server(host, port, registry) as server:
        server.serve_forever()
