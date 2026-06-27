"""URL ingest adapter: fetch an HTML page and normalize it to a :class:`RawDoc`.

The deterministic, fixture-tested core is :func:`parse_html`: it drops
non-prose markup (``script``/``style``/``head``), turns ``<h1>``..``<h6>`` into
Markdown ``#`` headings so the extractor can see concept boundaries, and
collapses whitespace. :func:`fetch_url` is the thin network wrapper (standard
library ``urllib`` only) that pulls the bytes and delegates to
:func:`parse_html`; it touches the network and is therefore not unit-tested.
"""

from __future__ import annotations

from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.request import Request, urlopen

from kosha.model import RawDoc, Source, SourceKind

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


def fetch_url(url: str, *, authority_rank: int = 0, timeout: float = 30.0) -> RawDoc:
    """Fetch ``url`` over HTTP(S) and normalize it to a :class:`RawDoc`."""
    request = Request(url, headers={"User-Agent": "kosha-ingest"})
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        html = response.read().decode(charset, errors="replace")
    return parse_html(
        html,
        url=url,
        authority_rank=authority_rank,
        retrieved_at=datetime.now(UTC),
    )


def _normalize(text: str) -> str:
    """Collapse intra-line whitespace and drop blank lines, keeping headings."""
    lines = (" ".join(line.split()) for line in text.splitlines())
    return "\n".join(line for line in lines if line)
