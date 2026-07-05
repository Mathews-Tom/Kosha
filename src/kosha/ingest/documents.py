"""Optional PDF/DOCX document ingest adapters.

Import this module only when the ``documents`` extra is installed. The package
root and ``kosha.ingest`` intentionally do not import it, so ``pypdf`` and
``python-docx`` never enter the core install or import graph.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from docx import Document
from pypdf import PdfReader

from kosha.ingest.guardrails import (
    DEFAULT_INGEST_POLICY,
    IngestPolicy,
    build_raw_doc,
    read_bytes_bounded,
)
from kosha.model import RawDoc, Source, SourceKind

_SUPPORTED_SUFFIXES = frozenset({".pdf", ".docx"})


class DocumentIngestError(ValueError):
    """Raised when a document export is unsupported or has no extractable text."""


def ingest_documents(
    source: Path,
    *,
    authority_rank: int = 0,
    policy: IngestPolicy = DEFAULT_INGEST_POLICY,
) -> list[RawDoc]:
    """Ingest one PDF/DOCX file or a directory containing PDF/DOCX files."""

    if source.is_file():
        return [
            _ingest_document_file(
                source,
                source_id=f"document:{source.name}",
                authority_rank=authority_rank,
                policy=policy,
            )
        ]
    if not source.is_dir():
        raise FileNotFoundError(f"not a document file or directory: {source}")
    docs: list[RawDoc] = []
    for path in sorted(
        child
        for child in source.rglob("*")
        if child.is_file() and child.suffix.lower() in _SUPPORTED_SUFFIXES
    ):
        rel = path.relative_to(source).as_posix()
        docs.append(
            _ingest_document_file(
                path,
                source_id=f"document:{rel}",
                location=rel,
                authority_rank=authority_rank,
                policy=policy,
            )
        )
    return docs


def _ingest_document_file(
    path: Path,
    *,
    source_id: str,
    authority_rank: int,
    policy: IngestPolicy,
    location: str | None = None,
) -> RawDoc:
    suffix = path.suffix.lower()
    data = read_bytes_bounded(path, policy=policy)
    if suffix == ".pdf":
        text = _extract_pdf_text(data)
    elif suffix == ".docx":
        text = _extract_docx_text(data)
    else:
        raise DocumentIngestError(f"unsupported document extension {path.suffix!r}: {path}")
    if not text.strip():
        raise DocumentIngestError(f"document has no extractable text: {path}")
    source = Source(
        source_id=source_id,
        kind=SourceKind.DOCUMENT,
        location=location or path.name,
        title=path.stem,
        authority_rank=authority_rank,
    )
    return build_raw_doc(source=source, text=text, policy=policy)


def _extract_pdf_text(data: bytes) -> str:
    reader = PdfReader(BytesIO(data))
    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(str(text).strip())
    return "\n\n".join(pages)


def _extract_docx_text(data: bytes) -> str:
    document = Document(BytesIO(data))
    paragraphs = [str(paragraph.text).strip() for paragraph in document.paragraphs]
    return "\n\n".join(paragraph for paragraph in paragraphs if paragraph)
