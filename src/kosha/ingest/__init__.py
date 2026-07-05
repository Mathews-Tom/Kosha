"""Ingest adapters: turn a source into normalized :class:`~kosha.model.RawDoc`s.

All adapters cross the same guarded boundary: stable ``Source`` provenance,
bounded input size, and prompt-injection sanitization before a ``RawDoc`` reaches
the extractor.
"""

from __future__ import annotations

from kosha.ingest.folder import ingest_folder
from kosha.ingest.guardrails import (
    DEFAULT_INGEST_POLICY,
    IngestAdapter,
    IngestGuardrailError,
    IngestPolicy,
)
from kosha.ingest.url import fetch_url, parse_html

__all__ = [
    "DEFAULT_INGEST_POLICY",
    "IngestAdapter",
    "IngestGuardrailError",
    "IngestPolicy",
    "fetch_url",
    "ingest_folder",
    "parse_html",
]
