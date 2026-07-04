# MCP integration

Kosha's consumer surface is a traversal-only MCP server. It exposes a fixed set of tools that walk the bundle — and deliberately **no raw-text search endpoint** — so an MCP client can answer through traversal rather than grepping the file tree. This is an interface boundary: a host agent that also has generic filesystem tools is not sandboxed by Kosha today.

## Running the server

The `kosha-mcp` entry point starts a stdio MCP server over one bundle. It needs the `mcp` extra, which `uv sync` already installs.

```bash
# bundle as an argument
uv run kosha-mcp bundles/northwind

# or via the environment
KOSHA_BUNDLE=bundles/northwind uv run kosha-mcp
```

On start it loads the bundle, builds the embedding index (for the jump), and serves the five tools over stdio. With neither an argument nor `KOSHA_BUNDLE`, it exits with a usage message.

## The traversal tools

Inside the MCP surface, these five tools are the way to read the knowledge base. They mirror the hybrid retrieval path: **jump** near the answer, then **traverse** to expand and verify.

| Tool | Signature | Returns |
|---|---|---|
| `find_concepts` | `(query: str, k: int = 3)` | Ranked candidate `concept_id`s + descriptions (the embedding jump) |
| `list_index` | `(scope: str = "")` | Structured listing of a directory's subdirectories and concepts (`""` is the root) |
| `read_frontmatter` | `(concept_id: str)` | `type`, `title`, `description`, `tags`, `timestamp`, effective dates, `access_level` — no body |
| `load_concept` | `(concept_id: str, asof: str \| None = None)` | Concept body, filtered to the claims in force |
| `follow_links` | `(concept_id: str)` | Out-links and backlinks, each flagged present or dangling |

### The intended flow

```mermaid
sequenceDiagram
    actor Agent
    participant MCP as kosha-mcp
    Agent->>MCP: find_concepts("Gold member return window")
    MCP-->>Agent: ranked candidates (the jump)
    Agent->>MCP: read_frontmatter(candidate)
    MCP-->>Agent: type / description / effective dates
    Agent->>MCP: load_concept(candidate)
    MCP-->>Agent: body (in-force claims only)
    opt expand / verify
        Agent->>MCP: follow_links(candidate)
        MCP-->>Agent: neighbors + backlinks
    end
    Agent->>Agent: answer from the minimal concept set
```

`list_index` is available for cold navigation and audit when the agent prefers structured traversal over the jump.

## Connecting a client

Any MCP client that can launch a stdio server works. Register `kosha-mcp` as the command. Example for a Claude Desktop-style `mcpServers` config:

```json
{
  "mcpServers": {
    "kosha": {
      "command": "uv",
      "args": ["run", "kosha-mcp"],
      "env": { "KOSHA_BUNDLE": "/abs/path/to/bundles/northwind" }
    }
  }
}
```

Point `command`/`args` at however you invoke the installed entry point in your environment (e.g. an absolute path to `kosha-mcp`), and give `KOSHA_BUNDLE` an absolute path. The server's tool list will appear as `find_concepts`, `list_index`, `read_frontmatter`, `load_concept`, `follow_links`.

The server also advertises instructions telling the agent to answer by traversal, jump with `find_concepts`, peek with `read_frontmatter`, load only what it needs, and treat the traversal tools as the only knowledge interface.

## Temporal validity

`load_concept` filters to the claims **in force now** by default: a claim whose `effective_to` has passed is hidden. Pass an ISO timestamp as `asof` to answer historical questions ("what was the policy in Q1"):

```text
load_concept("policies/returns/gold-members", asof="2026-01-15T00:00:00Z")
```

This is how one concept carries history without forking files — see [authoring bundles](authoring-bundles.md#temporal-validity).

## Access control (bundle-level)

Access is enforced at the **bundle level** — the bundle is granted or denied as a whole; there is no concept-level ACL (a deliberate v1 choice that keeps the "just files" portability story; see [system design §6](system_design.md)). The `KoshaKnowledgeService` accepts a required `bundle_access` label and a caller `clearance` set; when `bundle_access` is set, only a caller whose clearance contains it is served, otherwise every read raises an access error.

The `kosha-mcp` entry point serves the bundle openly (no access label). To enforce bundle-level access, embed the service in your own server process:

```python
from pathlib import Path
from kosha.okf.load import load_bundle
from kosha.index.embedding import EmbeddingIndex
from kosha.providers import resolve_embedding_provider
from kosha.mcp.service import KoshaKnowledgeService
from kosha.mcp.server import build_server

bundle = load_bundle(Path("bundles/northwind"))
index = EmbeddingIndex.build(bundle, resolve_embedding_provider())
service = KoshaKnowledgeService(
    bundle, index, bundle_access="support-team", clearance={"support-team"}
)
build_server(service).run()
```

To keep some knowledge out of an agent's reach today, put it in a **separate bundle** with its own permission boundary rather than relying on per-file hiding.

## Without MCP: the fallback contract

Not every environment has MCP. The same traversal protocol ships as paste-in instructions so an agent can follow the same no-grep, load-minimal, temporal discipline against the files directly:

- **`AGENTS.md` fragment** — [`consumer/AGENTS.fragment.md`](../consumer/AGENTS.fragment.md). Paste into the consuming repo's `AGENTS.md`.
- **Skill** — [`consumer/kosha-traversal/SKILL.md`](../consumer/kosha-traversal/SKILL.md). Drop into an agent's skill directory.

Both are generated from a single source of truth (`kosha.mcp.fallback`), so the file-based protocol stays identical to the MCP tool surface. The rules in either case:

- **Do not grep, ripgrep, or full-text search** the bundle — traverse from `index.md` (and the embedding jump).
- **Do not load the whole corpus** — stop as soon as the loaded concepts answer the question.
- Honor temporal validity and access; cite the `concept_id`s used.
