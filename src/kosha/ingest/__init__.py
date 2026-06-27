"""Ingest adapters: turn a source into normalized :class:`~kosha.model.RawDoc`s.

Two deterministic adapters ship for the v1 build cut (system_design §8.1):

* :func:`fetch_url` / :func:`parse_html` — pull and normalize an HTML page, and
* :func:`ingest_folder` — read a local folder of Markdown source documents.

DB/BigQuery adapters are deliberately out of scope (the design's Skip list).
"""

from __future__ import annotations

from kosha.ingest.folder import ingest_folder
from kosha.ingest.url import fetch_url, parse_html

__all__ = [
    "fetch_url",
    "ingest_folder",
    "parse_html",
]
