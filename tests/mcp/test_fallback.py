"""The non-MCP fallback fragment/skill and the committed artifacts stay in sync."""

from __future__ import annotations

from pathlib import Path

from kosha.mcp.fallback import render_consumer_skill, render_fallback_fragment
from kosha.sync.agent_fragment import render_agent_fragment_section
from kosha.sync.public_claims import find_banned_claims

REPO = Path(__file__).resolve().parents[2]
FRAGMENT = REPO / "consumer" / "AGENTS.fragment.md"
SKILL = REPO / "consumer" / "kosha-traversal" / "SKILL.md"

TOOLS = ("find_concepts", "list_index", "read_frontmatter", "load_concept", "follow_links")


def test_fragment_names_every_traversal_tool() -> None:
    text = render_fallback_fragment()
    for tool in TOOLS:
        assert tool in text


def test_fragment_forbids_grep_and_whole_corpus() -> None:
    text = render_fallback_fragment().lower()
    assert "do not grep" in text
    assert "do not load the whole corpus" in text


def test_fragment_has_no_banned_claims() -> None:
    text = render_fallback_fragment()
    violations = find_banned_claims(text)
    assert not violations, "Fallback fragment contains banned public claims: " + repr(violations)


def test_rendered_section_has_markers() -> None:
    text = render_agent_fragment_section()
    assert "<!-- KOSHA_AGENT_FRAGMENT_START -->" in text
    assert "<!-- KOSHA_AGENT_FRAGMENT_END -->" in text
    assert render_fallback_fragment() in text


def test_skill_has_frontmatter_and_protocol() -> None:
    text = render_consumer_skill()
    assert text.startswith("---")
    assert "name: kosha-traversal" in text
    for tool in TOOLS:
        assert tool in text
    assert "do not grep" in text.lower()


def test_committed_artifacts_match_rendered_output() -> None:
    assert FRAGMENT.read_text(encoding="utf-8") == render_fallback_fragment()
    assert SKILL.read_text(encoding="utf-8") == render_consumer_skill()
