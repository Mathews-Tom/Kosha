# CLI reference

The `kosha` command is installed by `uv sync`; run it as `uv run kosha <command>`. A second entry point, `kosha-mcp`, runs the consumer MCP server ([MCP integration](mcp-integration.md)).

```text
kosha [--version] [-h] {validate,bench,eval,ingest} ...
```

With no subcommand, `kosha` prints help and exits 0. All commands resolve their model providers from the environment, defaulting to the offline local pair ([configuration](configuration.md)).

---

## `kosha validate`

```text
kosha validate <bundle>
```

Check an OKF bundle directory for v0.1 conformance. Applies the three conformance rules (parseable frontmatter, non-empty `type`, reserved-file structure) as errors and reports permissive concerns (broken cross-links, granularity) as non-failing warnings.

| Argument | Description |
|---|---|
| `bundle` | Path to the OKF bundle directory. |

**Exit code:** `0` when the bundle has no error-severity findings (warnings are allowed); non-zero otherwise. Use it as a CI gate.

```bash
uv run kosha validate bundles/northwind
# OK: bundles/northwind is OKF-conformant (0 warning(s))
```

---

## `kosha ingest`

```text
kosha ingest <source> [--bundle PATH] [--dry-run] [--yes] [--authority N]
```

Run the full maintenance loop on a source folder behind the **plan → approve → commit** gate: extract concepts → dedup-resolve against the bundle → merge through the claim layer → cross-link → detect contradictions → regenerate `index.md` / append `log.md` → assemble a change plan → route by graduated autonomy → write and commit on approval.

| Flag | Default | Description |
|---|---|---|
| `source` | — | Source folder (Markdown) to ingest. |
| `--bundle` | `bundles/northwind` | Target OKF bundle directory. |
| `--dry-run` | off | Build and print the plan; write nothing, commit nothing. |
| `--yes` | off | Approve the plan non-interactively (explicit human approval for the block lane). |
| `--authority` | `0` | Source authority rank for contradiction resolution; higher wins, ties escalate. |

**Approval semantics.** Auto- and skim-lane plans apply under delegated autonomy. A blocked plan (contradiction, deletion/supersede of a load-bearing claim, or low-confidence dedup) requires an explicit yes: pass `--yes`, answer the interactive prompt, or — with neither — the plan is rejected default-safe (nothing is written).

```bash
# Preview only
uv run kosha ingest ./updates --bundle bundles/northwind --dry-run

# Apply, treating the source as higher-authority than the wiki
uv run kosha ingest ./policy-docs --bundle bundles/northwind --authority 2 --yes
```

---

## `kosha bench`

```text
kosha bench [--bundle PATH] [--report PATH]
```

Run the premise-validation retrieval benchmark: compare **hybrid** (Kosha) retrieval against **RAG** and **long-context-with-raw-docs** on token cost, round-trips, latency, and recall, then evaluate the three kill signals (long-context erosion, traversal latency, dedup-by-prompt) and print a GO/NO-GO verdict.

| Flag | Default | Description |
|---|---|---|
| `--bundle` | `bundles/northwind` | Golden bundle to benchmark. |
| `--report` | none | Write the full premise report to this path. |

```bash
uv run kosha bench --bundle bundles/northwind --report PREMISE_REPORT.md
```

Strategy roles: `hybrid` and the embedding index are production components reused downstream; `rag` and `long_context` are benchmark-only baselines.

### `kosha bench acceptance`

```text
kosha bench acceptance [--bundle PATH] [--report PATH]
```

Gate the four MVP success criteria on the golden corpus. **Exit code `0` iff every criterion passes**, otherwise `1` — this is the release gate.

| Criterion | Checks |
|---|---|
| C1 token/latency | hybrid total tokens < raw-docs **and** tokens-per-recall < RAG; latency within 2× RAG |
| C2 duplicate-rate | re-ingesting the corpus yields ≈0 duplicates |
| C3 fidelity | no edit-drift across ≥20 sequential ingests |
| C4 contradiction-safety | 100% of injected contradictions resolved-or-escalated; 0 silent overwrites |

```bash
uv run kosha bench acceptance --report ACCEPTANCE_REPORT.md
```

---

## `kosha eval`

```text
kosha eval {extract,dedup,merge,relate,contradict} [--labels PATH] [...]
```

Score one LLM surface against its seed label file. Each surface has its own suite so quality is measured independently. (Running `kosha eval` with no surface exits `2`.)

| Subcommand | Scores | Default labels | Extra flags |
|---|---|---|---|
| `extract` | concept extractor vs granularity labels | `labels/granularity_seed.jsonl` | — |
| `dedup` | dedup precision/recall + repeated-ingest duplicate rate | `labels/dedup_seed.jsonl` | `--bundle` (default `bundles/northwind`) |
| `merge` | merge claim-targeting accuracy | `labels/merge_seed.jsonl` | — |
| `relate` | cross-linker link-discovery precision/recall/F1 | `labels/relate_seed.jsonl` | — |
| `contradict` | contradiction detection precision/recall/F1 | `labels/contradict_seed.jsonl` | — |

```bash
uv run kosha eval dedup --labels labels/dedup_seed.jsonl --bundle bundles/northwind
uv run kosha eval contradict
```

The same suites run under pytest via `uv run pytest evals -q`.

---

## `kosha-mcp`

```text
kosha-mcp <bundle-path>      # or set KOSHA_BUNDLE
```

Start the stdio MCP server over a bundle, exposing the five traversal tools and no raw-text search. Requires the `mcp` extra (installed by `uv sync`). Configuration and client setup: [MCP integration](mcp-integration.md).

```bash
uv run kosha-mcp bundles/northwind
KOSHA_BUNDLE=bundles/northwind uv run kosha-mcp
```

---

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success / conformant / all criteria passed |
| `1` | `bench acceptance` — at least one criterion failed |
| `2` | `eval` invoked with no surface subcommand |
| non-zero | `validate` — bundle has error-severity findings |
