"""Pure-service tests for the index and frontmatter traversal operations."""

from __future__ import annotations

import pytest

from kosha.mcp.service import ConceptNotFoundError, KoshaKnowledgeService


def _targets(view: object) -> set[str]:
    assert isinstance(view, dict)
    return {
        entry["target"] for section in view["sections"] for entry in section["entries"]
    }


def test_list_index_root_links_subdirectories(service: KoshaKnowledgeService) -> None:
    view = service.list_index()
    assert view["scope"] == ""
    targets = _targets(view)
    # Root lists each top-level directory via its own index.md, not the leaf docs.
    assert "policies/index" in targets
    assert "playbooks/index" in targets


def test_list_index_scope_lists_concepts_with_descriptions(
    service: KoshaKnowledgeService,
) -> None:
    view = service.list_index("policies/returns")
    entries = {e["target"]: e for s in view["sections"] for e in s["entries"]}
    assert "policies/returns/gold-members" in entries
    description = entries["policies/returns/gold-members"]["description"] or ""
    assert "45-day" in description


def test_read_frontmatter_returns_fields_without_body(
    service: KoshaKnowledgeService,
) -> None:
    fm = service.read_frontmatter("policies/returns/gold-members")
    assert fm["concept_id"] == "policies/returns/gold-members"
    assert fm["type"] == "Policy"
    assert fm["title"] == "Gold Member Returns"
    assert "returns" in fm["tags"]
    assert (fm["effective_from"] or "").startswith("2026-06-20T00:00:00")
    assert "body" not in fm


def test_read_frontmatter_unknown_concept_raises(
    service: KoshaKnowledgeService,
) -> None:
    with pytest.raises(ConceptNotFoundError):
        service.read_frontmatter("policies/nonexistent")
