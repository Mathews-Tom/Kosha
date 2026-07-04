"""URL ingest guardrails: scheme, SSRF, and response-size guards (M6 PR-5).

These exercise the pure validation/read helpers directly rather than
``fetch_url`` end to end, since the guard functions never touch the network
for a literal IP address (``socket.getaddrinfo`` just parses it) while a real
fetch would require a live endpoint.
"""

from __future__ import annotations

from io import BytesIO

import pytest

from kosha.ingest.url import (
    UrlIngestError,
    _read_bounded,
    _require_public_hostname,
    _require_public_http_url,
)


class _FakeResponse:
    """A minimal stand-in for http.client.HTTPResponse's chunked ``read``."""

    def __init__(self, body: bytes, *, chunk_size: int = 8) -> None:
        self._buffer = BytesIO(body)
        self._chunk_size = chunk_size

    def read(self, size: int) -> bytes:
        return self._buffer.read(min(size, self._chunk_size))


@pytest.mark.parametrize("scheme", ["ftp", "file", "gopher", "data", "javascript"])
def test_disallowed_schemes_are_rejected(scheme: str) -> None:
    with pytest.raises(UrlIngestError, match="disallowed URL scheme"):
        _require_public_http_url(f"{scheme}://example.com/x")


@pytest.mark.parametrize("scheme", ["http", "https"])
def test_allowed_schemes_pass_scheme_validation(scheme: str) -> None:
    # example.com's own address is public; no SSRF guard should trip.
    _require_public_http_url(f"{scheme}://93.184.216.34/")


def test_url_with_no_hostname_is_rejected() -> None:
    with pytest.raises(UrlIngestError, match="no hostname"):
        _require_public_http_url("http:///path-only")


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",  # loopback
        "169.254.169.254",  # cloud metadata (AWS/GCP/Azure)
        "10.0.0.5",  # private
        "172.16.0.5",  # private
        "192.168.1.1",  # private
        "0.0.0.0",  # unspecified
        "224.0.0.1",  # multicast
        "::1",  # loopback (IPv6)
        "fc00::1",  # unique local (IPv6)
        "fe80::1",  # link-local (IPv6)
    ],
)
def test_internal_and_metadata_addresses_are_rejected(address: str) -> None:
    with pytest.raises(UrlIngestError, match="non-public address"):
        _require_public_hostname(address)


def test_a_public_ip_literal_is_accepted() -> None:
    _require_public_hostname("93.184.216.34")  # example.com


def test_unresolvable_hostname_fails_loud() -> None:
    with pytest.raises(UrlIngestError, match="could not resolve"):
        _require_public_hostname("this-host-does-not-exist.invalid")


def test_read_bounded_returns_the_full_body_under_the_cap() -> None:
    body = b"a" * 100
    result = _read_bounded(_FakeResponse(body), url="http://x", max_bytes=1000)
    assert result == body


def test_read_bounded_fails_loud_when_the_body_exceeds_the_cap() -> None:
    body = b"a" * 100
    with pytest.raises(UrlIngestError, match="exceeded max_bytes"):
        _read_bounded(_FakeResponse(body), url="http://x", max_bytes=50)


def test_read_bounded_accepts_a_body_exactly_at_the_cap() -> None:
    body = b"a" * 50
    result = _read_bounded(_FakeResponse(body), url="http://x", max_bytes=50)
    assert result == body
