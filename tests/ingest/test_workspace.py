"""Local workspace export adapter tests (PR-2): Confluence, Notion, Slack.

These adapters read local export files only -- no SaaS APIs, no credentials,
no network. Every test uses ``tmp_path`` fixtures to build a minimal export
shape and asserts on the guarded ``RawDoc``/``Source`` contract the adapters
promise: stable ``source_id`` provenance, ``SourceKind.WORKSPACE_EXPORT``,
authority-rank passthrough, and the shared size/sanitization guardrails.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kosha.ingest import (
    IngestGuardrailError,
    IngestPolicy,
    WorkspaceExportError,
    ingest_confluence_export,
    ingest_notion_export,
    ingest_slack_export,
)
from kosha.model import SourceKind

# --------------------------------------------------------------------------
# Confluence: local Markdown export
# --------------------------------------------------------------------------


def test_ingest_confluence_markdown_reads_sorted_docs_with_stable_ids(tmp_path: Path) -> None:
    # Created out of alphabetical order so the assertion only passes if the
    # adapter actually sorts, rather than replaying filesystem iteration order.
    (tmp_path / "b.md").write_text("# Beta\n\nBeta body.", encoding="utf-8")
    (tmp_path / "a.md").write_text("# Alpha\n\nAlpha body.", encoding="utf-8")

    docs = ingest_confluence_export(tmp_path, authority_rank=5)

    assert [doc.source.source_id for doc in docs] == ["confluence:a.md", "confluence:b.md"]
    alpha = docs[0]
    assert alpha.source.kind is SourceKind.WORKSPACE_EXPORT
    assert alpha.source.location == "a.md"
    assert alpha.source.title == "Alpha"
    assert alpha.source.authority_rank == 5
    assert "Alpha body." in alpha.text


def test_ingest_confluence_markdown_nested_paths_use_posix_relative_ids(tmp_path: Path) -> None:
    nested = tmp_path / "space" / "page"
    nested.mkdir(parents=True)
    (nested / "child.md").write_text("Untitled body only.", encoding="utf-8")

    docs = ingest_confluence_export(tmp_path)

    assert docs[0].source.source_id == "confluence:space/page/child.md"
    assert docs[0].source.location == "space/page/child.md"
    # No leading '#' heading -> title falls back to the file stem.
    assert docs[0].source.title == "child"


def test_ingest_confluence_markdown_strips_hidden_unicode(tmp_path: Path) -> None:
    (tmp_path / "page.md").write_text("# Page\n\nvisible\u200btext", encoding="utf-8")

    docs = ingest_confluence_export(tmp_path)

    assert docs[0].text == "# Page\n\nvisibletext"


def test_ingest_confluence_markdown_fails_loud_over_max_bytes(tmp_path: Path) -> None:
    (tmp_path / "big.md").write_text("# Big\n\n" + "x" * 1000, encoding="utf-8")

    with pytest.raises(IngestGuardrailError):
        ingest_confluence_export(tmp_path, policy=IngestPolicy(max_bytes=50))


# --------------------------------------------------------------------------
# Confluence: page JSON export
# --------------------------------------------------------------------------


def test_ingest_confluence_json_accepts_a_single_object_page(tmp_path: Path) -> None:
    (tmp_path / "page.json").write_text(
        json.dumps({"id": "42", "title": "Runbook", "body": "Do the thing."}),
        encoding="utf-8",
    )

    docs = ingest_confluence_export(tmp_path, authority_rank=3)

    assert len(docs) == 1
    doc = docs[0]
    assert doc.source.source_id == "confluence:42"
    assert doc.source.location == "page.json#42"
    assert doc.source.title == "Runbook"
    assert doc.source.kind is SourceKind.WORKSPACE_EXPORT
    assert doc.source.authority_rank == 3
    assert doc.text == "Do the thing."


def test_ingest_confluence_json_accepts_a_list_of_pages_and_falls_back_to_content(
    tmp_path: Path,
) -> None:
    pages = [
        {"id": "1", "title": "First", "body": "First body."},
        {"id": "2", "title": "Second", "content": "Second content."},
    ]
    (tmp_path / "pages.json").write_text(json.dumps(pages), encoding="utf-8")

    docs = ingest_confluence_export(tmp_path)

    assert [doc.source.source_id for doc in docs] == ["confluence:1", "confluence:2"]
    assert docs[0].source.location == "pages.json#1"
    assert docs[1].source.location == "pages.json#2"
    assert docs[1].text == "Second content."


@pytest.mark.parametrize(
    ("page", "missing_field"),
    [
        ({"title": "First", "body": "Body."}, "id"),
        ({"id": "1", "body": "Body."}, "title"),
    ],
)
def test_ingest_confluence_json_requires_id_and_title(
    tmp_path: Path, page: dict[str, str], missing_field: str
) -> None:
    (tmp_path / "page.json").write_text(json.dumps(page), encoding="utf-8")

    with pytest.raises(WorkspaceExportError, match=missing_field):
        ingest_confluence_export(tmp_path)


def test_ingest_confluence_json_requires_body_or_content(tmp_path: Path) -> None:
    (tmp_path / "page.json").write_text(
        json.dumps({"id": "1", "title": "First"}), encoding="utf-8"
    )

    with pytest.raises(WorkspaceExportError, match="'body' or 'content'"):
        ingest_confluence_export(tmp_path)


def test_ingest_confluence_json_rejects_a_non_object_page(tmp_path: Path) -> None:
    (tmp_path / "page.json").write_text(json.dumps(["not-an-object"]), encoding="utf-8")

    with pytest.raises(WorkspaceExportError, match="must be a JSON object"):
        ingest_confluence_export(tmp_path)


def test_ingest_confluence_json_strips_hidden_unicode_from_body(tmp_path: Path) -> None:
    (tmp_path / "page.json").write_text(
        json.dumps({"id": "1", "title": "Page", "body": "visible\u200btext"}),
        encoding="utf-8",
    )

    docs = ingest_confluence_export(tmp_path)

    assert docs[0].text == "visibletext"


def test_ingest_confluence_json_fails_loud_over_max_bytes(tmp_path: Path) -> None:
    (tmp_path / "page.json").write_text(
        json.dumps({"id": "1", "title": "Big", "body": "x" * 1000}), encoding="utf-8"
    )

    with pytest.raises(IngestGuardrailError):
        ingest_confluence_export(tmp_path, policy=IngestPolicy(max_bytes=50))


def test_ingest_confluence_export_rejects_malformed_json(tmp_path: Path) -> None:
    (tmp_path / "broken.json").write_text("{not valid json", encoding="utf-8")

    with pytest.raises(WorkspaceExportError, match="malformed JSON export"):
        ingest_confluence_export(tmp_path)


# --------------------------------------------------------------------------
# Notion: local Markdown export directory
# --------------------------------------------------------------------------


def test_ingest_notion_export_preserves_nested_relative_source_ids(tmp_path: Path) -> None:
    nested = tmp_path / "Engineering" / "Runbooks"
    nested.mkdir(parents=True)
    (nested / "Deploys.md").write_text("# Deploys\n\nDeploy steps.", encoding="utf-8")
    (tmp_path / "Home.md").write_text("# Home\n\nWelcome.", encoding="utf-8")

    docs = ingest_notion_export(tmp_path, authority_rank=2)

    by_id = {doc.source.source_id for doc in docs}
    assert by_id == {"notion:Engineering/Runbooks/Deploys.md", "notion:Home.md"}
    nested_doc = next(doc for doc in docs if doc.source.source_id.endswith("Deploys.md"))
    assert nested_doc.source.location == "Engineering/Runbooks/Deploys.md"
    assert nested_doc.source.kind is SourceKind.WORKSPACE_EXPORT
    assert nested_doc.source.authority_rank == 2
    assert nested_doc.source.title == "Deploys"


def test_ingest_notion_export_strips_hidden_unicode(tmp_path: Path) -> None:
    (tmp_path / "page.md").write_text("visible\u200btext", encoding="utf-8")

    docs = ingest_notion_export(tmp_path)

    assert docs[0].text == "visibletext"


def test_ingest_notion_export_fails_loud_over_max_bytes(tmp_path: Path) -> None:
    (tmp_path / "big.md").write_text("# Big\n\n" + "x" * 1000, encoding="utf-8")

    with pytest.raises(IngestGuardrailError):
        ingest_notion_export(tmp_path, policy=IngestPolicy(max_bytes=50))


# --------------------------------------------------------------------------
# Slack: channel/day JSON export
# --------------------------------------------------------------------------


def test_ingest_slack_export_combines_messages_into_deterministic_text(tmp_path: Path) -> None:
    channel = tmp_path / "general"
    channel.mkdir()
    messages = [
        {"ts": "1700000000.000100", "user": "alice", "text": "hello"},
        {"ts": "1700000001.000200", "text": "no user field"},
    ]
    (channel / "2024-01-01.json").write_text(json.dumps(messages), encoding="utf-8")

    docs = ingest_slack_export(tmp_path, authority_rank=9)

    assert len(docs) == 1
    doc = docs[0]
    assert doc.source.source_id == "slack:general/2024-01-01"
    assert doc.source.location == "general/2024-01-01.json"
    assert doc.source.kind is SourceKind.WORKSPACE_EXPORT
    assert doc.source.title == "Slack general 2024-01-01"
    assert doc.source.authority_rank == 9
    assert doc.text == (
        "[1700000000.000100] alice: hello\n[1700000001.000200] unknown: no user field"
    )


def test_ingest_slack_export_is_deterministic(tmp_path: Path) -> None:
    channel = tmp_path / "general"
    channel.mkdir()
    (channel / "2024-01-01.json").write_text(
        json.dumps([{"ts": "1", "text": "hi"}]), encoding="utf-8"
    )

    assert ingest_slack_export(tmp_path) == ingest_slack_export(tmp_path)


def test_ingest_slack_export_rejects_an_empty_message_array(tmp_path: Path) -> None:
    channel = tmp_path / "general"
    channel.mkdir()
    (channel / "2024-01-01.json").write_text("[]", encoding="utf-8")

    with pytest.raises(WorkspaceExportError, match="contains no messages"):
        ingest_slack_export(tmp_path)


def test_ingest_slack_export_rejects_a_non_array_payload(tmp_path: Path) -> None:
    channel = tmp_path / "general"
    channel.mkdir()
    (channel / "2024-01-01.json").write_text(
        json.dumps({"ts": "1", "text": "hi"}), encoding="utf-8"
    )

    with pytest.raises(WorkspaceExportError, match="must be a JSON array of messages"):
        ingest_slack_export(tmp_path)


@pytest.mark.parametrize(
    ("message", "missing_field"),
    [
        ({"text": "hi", "user": "alice"}, "ts"),
        ({"ts": "1", "user": "alice"}, "text"),
    ],
)
def test_ingest_slack_export_requires_ts_and_text_per_message(
    tmp_path: Path, message: dict[str, str], missing_field: str
) -> None:
    channel = tmp_path / "general"
    channel.mkdir()
    (channel / "2024-01-01.json").write_text(json.dumps([message]), encoding="utf-8")

    with pytest.raises(WorkspaceExportError, match=missing_field):
        ingest_slack_export(tmp_path)


def test_ingest_slack_export_rejects_a_non_object_message(tmp_path: Path) -> None:
    channel = tmp_path / "general"
    channel.mkdir()
    (channel / "2024-01-01.json").write_text(json.dumps(["not-an-object"]), encoding="utf-8")

    with pytest.raises(WorkspaceExportError, match="must be a JSON object"):
        ingest_slack_export(tmp_path)


def test_ingest_slack_export_strips_hidden_unicode_from_message_text(tmp_path: Path) -> None:
    channel = tmp_path / "general"
    channel.mkdir()
    messages = [{"ts": "1", "text": "visible\u200btext"}]
    (channel / "2024-01-01.json").write_text(json.dumps(messages), encoding="utf-8")

    docs = ingest_slack_export(tmp_path)

    assert docs[0].text == "[1] unknown: visibletext"


def test_ingest_slack_export_fails_loud_over_max_bytes(tmp_path: Path) -> None:
    channel = tmp_path / "general"
    channel.mkdir()
    messages = [{"ts": "1", "text": "x" * 1000}]
    (channel / "2024-01-01.json").write_text(json.dumps(messages), encoding="utf-8")

    with pytest.raises(IngestGuardrailError):
        ingest_slack_export(tmp_path, policy=IngestPolicy(max_bytes=50))


def test_ingest_slack_export_rejects_malformed_json(tmp_path: Path) -> None:
    channel = tmp_path / "general"
    channel.mkdir()
    (channel / "2024-01-01.json").write_text("[1, 2,", encoding="utf-8")

    with pytest.raises(WorkspaceExportError, match="malformed JSON export"):
        ingest_slack_export(tmp_path)
