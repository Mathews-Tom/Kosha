"""URL ingest adapter: fetch an HTML page and normalize it to a :class:`RawDoc`.

The deterministic, fixture-tested core is :func:`parse_html`: it drops
non-prose markup (``script``/``style``/``head``), turns ``<h1>``..``<h6>`` into
Markdown ``#`` headings so the extractor can see concept boundaries, and
collapses whitespace. :func:`fetch_url` is the thin network wrapper (standard
library ``urllib`` only) that pulls the bytes and delegates to
:func:`parse_html`.

A caller-supplied, agent-triggerable URL is an SSRF surface: resolve-then-
connect against an attacker-chosen host can reach a cloud metadata endpoint
(e.g. ``169.254.169.254``) or an internal-only service just as easily as a
public page. :func:`fetch_url` therefore validates the scheme and resolves
the hostname, rejecting any address in a loopback, link-local, private, or
otherwise non-global range before ever opening a connection, and bounds the
response size so an oversized or slow-drip response cannot exhaust memory.
"""

from __future__ import annotations

import ipaddress
import socket
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Protocol
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from kosha.model import RawDoc, Source, SourceKind

_ALLOWED_SCHEMES = frozenset({"http", "https"})
_DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10 MiB
_READ_CHUNK_BYTES = 65536


class UrlIngestError(ValueError):
    """Raised when a URL fails the scheme, SSRF, or response-size guard."""


class _ChunkReadable(Protocol):
    """The subset of ``http.client.HTTPResponse`` that ``_read_bounded`` needs."""

    def read(self, size: int) -> bytes: ...


# Tags whose text content is never document prose.
_SKIP_TAGS = frozenset({"script", "style", "head", "title", "noscript"})
# Block-level tags that introduce a line break in the normalized text.
_BLOCK_TAGS = frozenset(
    {
        "p", "div", "section", "article", "header", "footer", "br", "li",
        "tr", "ul", "ol", "table", "blockquote",
    }
)
# Heading tags mapped to their Markdown ``#`` depth.
_HEADING_LEVELS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}


class _TextExtractor(HTMLParser):
    """Collect prose text and the document title from an HTML stream."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip_depth = 0
        self._in_title = False
        self._title: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
            if tag == "title":
                self._in_title = True
            return
        level = _HEADING_LEVELS.get(tag)
        if level is not None:
            self._chunks.append("\n" + "#" * level + " ")
        elif tag in _BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS:
            if self._skip_depth:
                self._skip_depth -= 1
            if tag == "title":
                self._in_title = False
            return
        if tag in _HEADING_LEVELS or tag in _BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if self._in_title and self._title is None:
            stripped = data.strip()
            if stripped:
                self._title = stripped
        if self._skip_depth:
            return
        self._chunks.append(data)

    @property
    def text(self) -> str:
        return "".join(self._chunks)

    @property
    def title(self) -> str | None:
        return self._title


def parse_html(
    html: str,
    *,
    url: str,
    authority_rank: int = 0,
    retrieved_at: datetime | None = None,
) -> RawDoc:
    """Normalize ``html`` into a :class:`RawDoc` (deterministic, no network)."""
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    source = Source(
        source_id=url,
        kind=SourceKind.URL,
        location=url,
        title=parser.title,
        authority_rank=authority_rank,
        retrieved_at=retrieved_at,
    )
    return RawDoc(source=source, text=_normalize(parser.text))


def fetch_url(
    url: str,
    *,
    authority_rank: int = 0,
    timeout: float = 30.0,
    max_bytes: int = _DEFAULT_MAX_BYTES,
) -> RawDoc:
    """Fetch ``url`` over HTTP(S) and normalize it to a :class:`RawDoc`.

    Fails loud (:class:`UrlIngestError`) on a disallowed scheme, a hostname
    that resolves to a non-public address, or a response exceeding
    ``max_bytes``, rather than silently truncating or fetching an
    internal-network target.
    """
    _require_public_http_url(url)
    request = Request(url, headers={"User-Agent": "kosha-ingest"})
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        raw = _read_bounded(response, url=url, max_bytes=max_bytes)
        html = raw.decode(charset, errors="replace")
    return parse_html(
        html,
        url=url,
        authority_rank=authority_rank,
        retrieved_at=datetime.now(UTC),
    )


def _require_public_http_url(url: str) -> None:
    """Reject a disallowed scheme or a hostname resolving to a non-public address."""
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise UrlIngestError(f"disallowed URL scheme {scheme!r}; only http/https are permitted")
    hostname = parts.hostname
    if not hostname:
        raise UrlIngestError(f"URL has no hostname: {url!r}")
    _require_public_hostname(hostname)


def _require_public_hostname(hostname: str) -> None:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise UrlIngestError(f"could not resolve hostname {hostname!r}: {exc}") from exc
    if not infos:
        raise UrlIngestError(f"hostname {hostname!r} resolved to no addresses")
    for info in infos:
        raw_address = info[4][0]
        address = ipaddress.ip_address(raw_address)
        if _is_non_public(address):
            raise UrlIngestError(
                f"hostname {hostname!r} resolves to a non-public address "
                f"{raw_address}; internal-network and cloud-metadata targets "
                "are not permitted"
            )


def _is_non_public(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def _read_bounded(response: _ChunkReadable, *, url: str, max_bytes: int) -> bytes:
    """Read ``response`` up to ``max_bytes``, failing loud rather than truncating."""
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = response.read(_READ_CHUNK_BYTES)
        if not chunk:
            return b"".join(chunks)
        total += len(chunk)
        if total > max_bytes:
            raise UrlIngestError(f"response from {url!r} exceeded max_bytes={max_bytes}")
        chunks.append(chunk)


def _normalize(text: str) -> str:
    """Collapse intra-line whitespace and drop blank lines, keeping headings."""
    lines = (" ".join(line.split()) for line in text.splitlines())
    return "\n".join(line for line in lines if line)
