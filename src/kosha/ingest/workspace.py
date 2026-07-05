"""Local workspace export adapters for Confluence, Notion, and Slack.

These adapters intentionally read local export files only. They do not call SaaS
APIs, accept credentials, or follow remote links. Each adapter maps the vendor
export shape into guarded :class:`kosha.model.RawDoc` objects with stable
``Source.source_id`` provenance.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from kosha.ingest.folder import _leading_heading
from kosha.ingest.guardrails import (
    DEFAULT_INGEST_POLICY,
    IngestPolicy,
    build_raw_doc,
    read_text_file_bounded,
)
from kosha.model import RawDoc, Source, SourceKind


class WorkspaceExportError(ValueError):
    """Raised when a local workspace export does not match a supported shape."""


def ingest_confluence_export(
    root: Path,
    *,
    authority_rank: int = 0,
    policy: IngestPolicy = DEFAULT_INGEST_POLICY,
) -> list[RawDoc]:
    """Ingest Confluence-style local Markdown files or page JSON files."""

    _require_directory(root)
    docs: list[RawDoc] = []
    for path in _sorted_files(root, {".md", ".json"}):
        rel = path.relative_to(root).as_posix()
        if path.suffix == ".md":
            text = read_text_file_bounded(path, policy=policy)
            source = Source(
                source_id=f"confluence:{rel}",
                kind=SourceKind.WORKSPACE_EXPORT,
                location=rel,
                title=_leading_heading(text) or path.stem,
                authority_rank=authority_rank,
            )
            docs.append(build_raw_doc(source=source, text=text, policy=policy))
            continue
        docs.extend(
            _confluence_docs_from_json(
                path,
                root=root,
                authority_rank=authority_rank,
                policy=policy,
            )
        )
    return docs


def ingest_notion_export(
    root: Path,
    *,
    authority_rank: int = 0,
    policy: IngestPolicy = DEFAULT_INGEST_POLICY,
) -> list[RawDoc]:
    """Ingest a Notion-style local Markdown export directory."""

    _require_directory(root)
    docs: list[RawDoc] = []
    for path in _sorted_files(root, {".md"}):
        rel = path.relative_to(root).as_posix()
        text = read_text_file_bounded(path, policy=policy)
        source = Source(
            source_id=f"notion:{rel}",
            kind=SourceKind.WORKSPACE_EXPORT,
            location=rel,
            title=_leading_heading(text) or path.stem,
            authority_rank=authority_rank,
        )
        docs.append(build_raw_doc(source=source, text=text, policy=policy))
    return docs


def ingest_slack_export(
    root: Path,
    *,
    authority_rank: int = 0,
    policy: IngestPolicy = DEFAULT_INGEST_POLICY,
) -> list[RawDoc]:
    """Ingest Slack-style local channel/day JSON exports."""

    _require_directory(root)
    docs: list[RawDoc] = []
    for path in _sorted_files(root, {".json"}):
        rel = path.relative_to(root).as_posix()
        messages = _json_sequence(path, policy=policy)
        if not messages:
            raise WorkspaceExportError(f"Slack export {path} contains no messages")
        lines: list[str] = []
        for index, item in enumerate(messages):
            message = _require_mapping(item, path=path, label=f"message[{index}]")
            ts = _required_str(message, "ts", path=path)
            text = _required_str(message, "text", path=path)
            user = _optional_str(message, "user") or "unknown"
            lines.append(f"[{ts}] {user}: {text}")
        channel = path.parent.name if path.parent != root else path.stem
        source = Source(
            source_id=f"slack:{rel.removesuffix('.json')}",
            kind=SourceKind.WORKSPACE_EXPORT,
            location=rel,
            title=f"Slack {channel} {path.stem}",
            authority_rank=authority_rank,
        )
        docs.append(build_raw_doc(source=source, text="\n".join(lines), policy=policy))
    return docs


def _confluence_docs_from_json(
    path: Path,
    *,
    root: Path,
    authority_rank: int,
    policy: IngestPolicy,
) -> list[RawDoc]:
    rel = path.relative_to(root).as_posix()
    payload = _json_payload(path, policy=policy)
    pages: Sequence[object] = payload if isinstance(payload, list) else [payload]
    docs: list[RawDoc] = []
    for index, item in enumerate(pages):
        page = _require_mapping(item, path=path, label=f"page[{index}]")
        page_id = _required_str(page, "id", path=path)
        title = _required_str(page, "title", path=path)
        text = _page_text(page, path=path)
        source = Source(
            source_id=f"confluence:{page_id}",
            kind=SourceKind.WORKSPACE_EXPORT,
            location=f"{rel}#{page_id}",
            title=title,
            authority_rank=authority_rank,
        )
        docs.append(build_raw_doc(source=source, text=text, policy=policy))
    return docs


def _page_text(page: Mapping[str, object], *, path: Path) -> str:
    body = page.get("body")
    if isinstance(body, str):
        return body
    content = page.get("content")
    if isinstance(content, str):
        return content
    raise WorkspaceExportError(
        f"Confluence export {path} page must contain string 'body' or 'content'"
    )


def _json_sequence(path: Path, *, policy: IngestPolicy) -> Sequence[object]:
    payload = _json_payload(path, policy=policy)
    if not isinstance(payload, list):
        raise WorkspaceExportError(f"Slack export {path} must be a JSON array of messages")
    return payload


def _json_payload(path: Path, *, policy: IngestPolicy) -> object:
    raw = read_text_file_bounded(path, policy=policy)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise WorkspaceExportError(f"malformed JSON export {path}: {exc.msg}") from exc


def _sorted_files(root: Path, suffixes: set[str]) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix in suffixes)


def _require_directory(path: Path) -> None:
    if not path.is_dir():
        raise NotADirectoryError(f"not a workspace export directory: {path}")


def _require_mapping(item: object, *, path: Path, label: str) -> Mapping[str, object]:
    if not isinstance(item, Mapping):
        raise WorkspaceExportError(f"{label} in {path} must be a JSON object")
    return item


def _required_str(mapping: Mapping[str, object], key: str, *, path: Path) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise WorkspaceExportError(f"export {path} missing required string field {key!r}")
    return value


def _optional_str(mapping: Mapping[str, object], key: str) -> str | None:
    value = mapping.get(key)
    return value if isinstance(value, str) and value else None
