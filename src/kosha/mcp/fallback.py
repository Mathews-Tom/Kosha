"""Non-MCP consumer fallback: the traversal protocol as plain instructions.

When an agent cannot reach the Kosha MCP server, it can still consume the bundle
by *traversal* rather than ad hoc file search (system_design §6: "skill + AGENTS.md
fragment (fallbacks)"). This module is the single
source of truth for that fallback contract: :func:`render_fallback_fragment`
produces the paste-in ``AGENTS.md`` section and :func:`render_consumer_skill`
produces the companion ``SKILL.md``. The committed ``consumer/`` artifacts are
rendered from these functions (a test guards that they stay in sync).

The fallback mirrors the MCP bundle traversal surface (``find_concepts``,
``list_index``, ``read_frontmatter``, ``load_concept``, ``follow_links``,
``claim_history``) as file operations so the same temporal/access discipline and
the same no-grep rule hold without a server.
"""

from __future__ import annotations

_PROTOCOL = """\
- `find_concepts` → if an embedding index is available, jump to the few concepts \
nearest the question; otherwise start from the bundle-root `index.md`.
- `list_index` → read a directory's `index.md` to see its contents before opening \
any document. Descend one level at a time.
- `read_frontmatter` → read a concept's YAML frontmatter (type, description, \
effective dates) to judge relevance before loading its body.
- `load_concept` → read the concept body. Honor temporal validity: ignore any \
claim whose `effective_to` has passed (use the value in force now). Treat a \
concept you are not cleared to read as absent.
- `follow_links` → follow the standard markdown links in a concept body to reach \
related concepts; load only the neighbors you actually need.
- `claim_history` → inspect claim metadata (`claim_id`, `supersedes`, \
`contradicts`, `effective_from`, `effective_to`) in the concept frontmatter/body \
when you need an audit trail for an answer."""

_RULES = """\
- **Do not grep, ripgrep, or full-text search** the bundle. Traverse from \
`index.md` (and the embedding jump) instead.
- **Do not load the whole corpus.** Stop as soon as the loaded concepts answer \
the question.
- Cite the `concept_id`s you used."""

_FRAGMENT = f"""\
## Consuming this OKF knowledge bundle

This repository is an OKF knowledge bundle. Answer knowledge questions **only** by
traversing it, loading the smallest set of concepts that answers the question.

When the Kosha MCP server is connected, use its bundle traversal tools:
`find_concepts`, `list_index`, `read_frontmatter`, `load_concept`,
`follow_links`, `claim_history`. Without MCP,
perform the same traversal by hand against the files:

{_PROTOCOL}

Rules:
{_RULES}
"""

_SKILL = f"""\
---
name: kosha-traversal
description: Consume an OKF knowledge bundle by traversal (find_concepts, \
list_index, read_frontmatter, load_concept, follow_links, claim_history) and \
never by grepping or loading the whole corpus. Use when answering questions from \
a Kosha/OKF bundle, with or without the MCP server.
---

# Kosha traversal consumer

Answer questions from an OKF knowledge bundle by traversal, never by full-text
search. The bundle is a tree of concept documents with per-directory `index.md`
maps and standard bundle-relative markdown links between concepts.

## Protocol

{_PROTOCOL}

## Rules

{_RULES}
"""


def render_fallback_fragment() -> str:
    """Return the ``AGENTS.md`` fragment for non-MCP consumers."""
    return _FRAGMENT


def render_consumer_skill() -> str:
    """Return the companion ``SKILL.md`` for non-MCP consumers."""
    return _SKILL
