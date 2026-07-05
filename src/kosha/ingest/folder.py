"""Local Markdown folder ingest adapter.

Walks a directory for ``*.md`` files in sorted path order and turns each into a
:class:`RawDoc`. The ``source_id`` is the file path relative to the ingested
root, so ids are stable regardless of where the folder lives on disk — the
property the deterministic fixture tests rely on. The folder is treated as a raw
source (every ``*.md`` is ingested); it is not an OKF bundle, so ``index.md`` /
``log.md`` are not special here.
"""

from __future__ import annotations

from pathlib import Path

from kosha.ingest.guardrails import (
    DEFAULT_INGEST_POLICY,
    IngestPolicy,
    build_raw_doc,
    read_text_file_bounded,
)
from kosha.model import RawDoc, Source, SourceKind


def ingest_folder(
    root: Path,
    *,
    authority_rank: int = 0,
    policy: IngestPolicy = DEFAULT_INGEST_POLICY,
) -> list[RawDoc]:
    """Read every ``*.md`` under ``root`` into a deterministic list of RawDocs."""
    if not root.is_dir():
        raise NotADirectoryError(f"not a directory: {root}")
    docs: list[RawDoc] = []
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        text = read_text_file_bounded(path, policy=policy)
        source = Source(
            source_id=rel,
            kind=SourceKind.MARKDOWN,
            location=rel,
            title=_leading_heading(text) or path.stem,
            authority_rank=authority_rank,
        )
        docs.append(build_raw_doc(source=source, text=text, policy=policy))
    return docs


def _leading_heading(text: str) -> str | None:
    """Return the first line's heading text, or ``None`` if it is not a heading."""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or None
        return None
    return None
