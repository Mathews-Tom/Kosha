# Getting started

This guide takes you from a clean checkout to a running knowledge engine: validate a bundle, run an ingest through the maintenance loop, and serve it to an agent over MCP. Every command here is runnable against the bundled reference corpus.

## Prerequisites

- Python ≥ 3.12
- [`uv`](https://docs.astral.sh/uv/) (package and environment manager)
- Git (Kosha commits every approved ingest)

## Install

```bash
git clone <repo-url> kosha && cd kosha
uv sync
uv run kosha --version   # → kosha 0.1.0
```

`uv sync` provisions the runtime dependencies (`pydantic`, `pyyaml`), the MCP server (`mcp`), and the dev toolchain (`pytest`, `mypy`, `ruff`). All subsequent commands run inside that environment via `uv run`.

## 1. Look at the reference bundle

Kosha ships a small, realistic OKF corpus — a retailer's support knowledge — at `bundles/northwind`:

```text
bundles/northwind/
  index.md                 # bundle root: a table of contents (okf_version only)
  log.md                   # dated change history
  policies/
    index.md
    returns/
      index.md
      standard.md          # the standard 30-day return window
      gold-members.md      # a 45-day window for Gold members (temporal)
    refunds.md  shipping.md  exchanges.md
  playbooks/   entities/   references/
```

Open `bundles/northwind/index.md` — it is the map an agent reads first. Then open `policies/returns/gold-members.md` to see a concept: YAML frontmatter (`type`, `title`, `description`, `effective_from`) plus a body with bundle-relative markdown links. This is the artifact Kosha produces and maintains.

## 2. Validate conformance

The validator enforces the three OKF v0.1 conformance rules and exits non-zero on any violation, so it can gate CI:

```bash
uv run kosha validate bundles/northwind
# OK: bundles/northwind is OKF-conformant (0 warning(s))
```

Conformance failures (missing frontmatter, missing `type`, malformed reserved files) are errors. Permissive concerns — broken cross-links, concept granularity — are reported as warnings and never fail validation. See [authoring bundles](authoring-bundles.md) for the full rule set.

## 3. See the value — run the benchmark

The benchmark compares Kosha's hybrid retrieval against RAG and long-context-with-raw-docs on the corpus:

```bash
uv run kosha bench --bundle bundles/northwind
```

```text
Benchmark over bundles/northwind (8 queries, embed=lexical-hash-256, gen=extractive-3)
| Strategy     | Avg total tokens | Concept recall | Answer-keyword recall |
| hybrid       | 602              | 1.00           | 0.88                  |
| rag          | 541              | 0.62           | 0.62                  |
| long_context | 1131             | 1.00           | 0.75                  |
Premise verdict: GO
```

On this deterministic local-provider corpus, hybrid matches long-context recall at about half the tokens and beats RAG on recall at comparable cost. These numbers are self-consistency evidence, not real-model decision-quality evidence.

## 4. Run the maintenance loop — `kosha ingest`

This is the differentiator. Create a source folder with a knowledge update — say, a policy change:

```bash
mkdir -p /tmp/src/policies
cat > /tmp/src/policies/returns.md <<'EOF'
# Returns
Customers may return unworn items within 30 days of delivery for a full refund.
Gold members now get 45 days instead of 30.
EOF
```

**Preview first** with `--dry-run` — nothing is written or committed:

```bash
uv run kosha ingest /tmp/src --bundle bundles/northwind --dry-run
```

The plan shows each proposed change (CREATE / UPDATE / LINK / FLAG), how dedup resolved each draft, and which autonomy lane it routed to. Because the "return window" concept already exists, dedup proposes an **UPDATE**, not a duplicate file.

**Commit it** by approving. Auto/skim-lane plans apply under delegated autonomy; the block lane (contradictions, deletions, low confidence) needs an explicit `--yes`:

```bash
uv run kosha ingest /tmp/src --bundle bundles/northwind --yes
```

Kosha writes the changes on an ingest branch and commits them. The `--authority <n>` flag sets the source's authority rank, which the contradiction resolver uses when a new claim conflicts with an existing one (higher authority wins; ties escalate to you).

> The bundle is the system of record. Inspect what changed with `git diff` / `git log` in the bundle's repo.

## 5. Connect an agent over MCP

Serve a bundle through the traversal-only MCP server:

```bash
KOSHA_BUNDLE=bundles/northwind uv run kosha-mcp
```

This exposes five tools — `find_concepts`, `list_index`, `read_frontmatter`, `load_concept`, `follow_links` — and **no raw-text search endpoint**, so the MCP knowledge interface is traversal-first. Point an MCP client (e.g. Claude Desktop) at the `kosha-mcp` command; see [MCP integration](mcp-integration.md) for client config and the no-MCP fallback.

Ask the agent *"How long does a Gold member have to return boots?"* and it will jump with `find_concepts`, peek frontmatter, and load only `policies/returns/gold-members.md` (and maybe `membership-tier.md`) — never the playbooks or references.

## 6. Gate the success criteria

The acceptance harness proves the full MVP contract and exits non-zero if any criterion regresses:

```bash
uv run kosha bench acceptance --bundle bundles/northwind --report ACCEPTANCE_REPORT.md
```

```text
C1-token-latency:        PASS
C2-duplicate-rate:       PASS
C3-fidelity:             PASS
C4-contradiction-safety: PASS
MVP success contract: PASS
```

## Where to go next

- [CLI reference](cli-reference.md) — every command and flag.
- [Authoring bundles](authoring-bundles.md) — write conformant concepts by hand.
- [MCP integration](mcp-integration.md) — wire agents to the bundle.
- [Configuration](configuration.md) — swap in a real model provider.
- [System design](system_design.md) — how the loop is built and why.
