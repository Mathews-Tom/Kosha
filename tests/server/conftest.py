"""Test-only harness for the M9 sandboxed HTTP/SSE server (no production code here).

Mirrors tests/mcp/conftest.py's pattern (northwind bundle, LexicalEmbeddingProvider)
but builds a ``BundleRegistry`` and runs a real ``KoshaHttpServer`` on an
ephemeral loopback port so tests exercise the actual network boundary a
served client would talk to.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from http.client import HTTPConnection
from pathlib import Path

import pytest

from kosha.index.embedding import EmbeddingIndex
from kosha.mcp.service import KoshaKnowledgeService
from kosha.model import Bundle
from kosha.okf.load import load_bundle
from kosha.providers import LexicalEmbeddingProvider
from kosha.server.http import KoshaHttpServer, make_http_server
from kosha.server.registry import BundleRegistration, BundleRegistry

NORTHWIND = Path(__file__).resolve().parents[2] / "bundles" / "northwind"
GOOD_BUNDLE = Path(__file__).resolve().parent.parent / "fixtures" / "good_bundle"


def make_service(
    bundle: Bundle, *, bundle_access: str | None = None, clearance: tuple[str, ...] = ()
) -> KoshaKnowledgeService:
    index = EmbeddingIndex.build(bundle, LexicalEmbeddingProvider())
    return KoshaKnowledgeService(bundle, index, bundle_access=bundle_access, clearance=clearance)


@pytest.fixture
def northwind() -> Bundle:
    return load_bundle(NORTHWIND)


@pytest.fixture
def good_bundle() -> Bundle:
    return load_bundle(GOOD_BUNDLE)


@pytest.fixture
def registry(northwind: Bundle, good_bundle: Bundle) -> BundleRegistry:
    """One open bundle ("northwind") and one this server process never clears."""
    return BundleRegistry(
        [
            BundleRegistration("northwind", make_service(northwind)),
            BundleRegistration(
                "good", make_service(good_bundle, bundle_access="confidential")
            ),
        ]
    )


class RunningServer:
    """A KoshaHttpServer bound to an ephemeral loopback port, for one test."""

    def __init__(self, registry: BundleRegistry) -> None:
        self._server: KoshaHttpServer = make_http_server("127.0.0.1", 0, registry)
        self.port: int = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def connection(self) -> HTTPConnection:
        return HTTPConnection("127.0.0.1", self.port, timeout=5)

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


@pytest.fixture
def start_server() -> Iterator[Callable[[BundleRegistry], RunningServer]]:
    servers: list[RunningServer] = []

    def start(reg: BundleRegistry) -> RunningServer:
        server = RunningServer(reg)
        servers.append(server)
        return server

    yield start
    for server in servers:
        server.close()
