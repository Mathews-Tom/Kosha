"""Ingest adapters: turn a source into normalized :class:`~kosha.model.RawDoc`s.

All adapters cross the same guarded boundary: stable ``Source`` provenance,
bounded input size, and prompt-injection sanitization before a ``RawDoc`` reaches
the extractor.
"""

from __future__ import annotations

from kosha.ingest.folder import ingest_folder
from kosha.ingest.guardrails import (
    DEFAULT_INGEST_POLICY,
    EvidenceRun,
    IngestAdapter,
    IngestGuardrailError,
    IngestPolicy,
    bind_evidence,
    persist_evidence_run,
)
from kosha.ingest.url import fetch_url, parse_html
from kosha.ingest.workspace import (
    WorkspaceExportError,
    ingest_confluence_export,
    ingest_notion_export,
    ingest_slack_export,
)

__all__ = [
    "DEFAULT_INGEST_POLICY",
    "EvidenceRun",
    "IngestAdapter",
    "IngestGuardrailError",
    "IngestPolicy",
    "WorkspaceExportError",
    "bind_evidence",
    "fetch_url",
    "ingest_confluence_export",
    "ingest_folder",
    "ingest_notion_export",
    "ingest_slack_export",
    "parse_html",
    "persist_evidence_run",
]
