# CLI reference

The `kosha` command is installed by `uv sync`; run it as `uv run kosha <command>`. A second entry point, `kosha-mcp`, runs the consumer MCP server ([MCP integration](mcp-integration.md)).

```text
kosha [--version] [-h] {validate,bench,eval,ingest} ...
```

With no subcommand, `kosha` prints help and exits 0. All commands resolve their model providers from the environment, defaulting to the offline local pair ([configuration](configuration.md)). `validate`, `bench` (+ `acceptance`/`realworld`), `calibrate`, `ingest`, and every `eval` suite accept `--json` to print a structured, script-parseable result instead of the text report — see [CI integration](ci-integration.md) for the packaged validate-on-PR action.

---

## `kosha validate`

```text
kosha validate <bundle> [--json]
```

Check an OKF bundle directory for v0.1 conformance. Applies the three conformance rules (parseable frontmatter, non-empty `type`, reserved-file structure) as errors and reports permissive concerns (broken cross-links, granularity) as non-failing warnings.

| Argument | Description |
|---|---|
| `bundle` | Path to the OKF bundle directory. |

**Exit code:** `0` when the bundle has no error-severity findings (warnings are allowed); non-zero otherwise. Use it as a CI gate.

```bash
uv run kosha validate bundles/northwind
# OK: bundles/northwind is OKF-conformant (0 warning(s))

uv run kosha validate bundles/northwind --json
# {"bundle": "bundles/northwind", "conformant": true, "error_count": 0, "warning_count": 0, "findings": []}
```

---

## `kosha ingest`

```text
kosha ingest <source> [--bundle PATH] [--dry-run] [--yes] [--authority N] [--json]
```

Run the full maintenance loop on a source folder behind the **plan → approve → commit** gate: extract concepts → dedup-resolve against the bundle → merge through the claim layer → cross-link → detect contradictions → regenerate `index.md` / append `log.md` → assemble a change plan → route by graduated autonomy → write and commit on approval.

| Flag | Default | Description |
|---|---|---|
| `source` | — | Source folder (Markdown) to ingest. |
| `--bundle` | `bundles/northwind` | Target OKF bundle directory. |
| `--dry-run` | off | Build and print the plan; write nothing, commit nothing. |
| `--yes` | off | Approve the plan non-interactively (explicit human approval for the block lane). |
| `--authority` | `0` | Source authority rank for contradiction resolution; higher wins, ties escalate. |
| `--json` | off | Print the plan/routing/commit outcome as structured JSON instead of the text report. File content is never included. |

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
kosha bench [--bundle PATH] [--report PATH] [--json]
```

Run the deterministic local-provider premise-validation retrieval benchmark: compare **hybrid** (Kosha) retrieval against **RAG** and **long-context-with-raw-docs** on token cost, round-trips, latency, and recall, then evaluate the three reference-corpus kill signals (long-context erosion, traversal latency, dedup-by-prompt) and print a GO/NO-GO verdict.

| Flag | Default | Description |
|---|---|---|
| `--bundle` | `bundles/northwind` | Golden bundle to benchmark. |
| `--report` | none | Write the full premise report to this path. |
| `--json` | off | Print the strategy comparison and kill signals as structured JSON instead of the table/text report. |

```bash
uv run kosha bench --bundle bundles/northwind --report PREMISE_REPORT.md
```

Strategy roles: `hybrid` and the embedding index are production components reused downstream; `rag` and `long_context` are benchmark-only baselines.

### `kosha bench acceptance`

```text
kosha bench acceptance [--bundle PATH] [--report PATH] [--json]
```

Gate the five MVP success criteria on the golden corpus. **Exit code `0` iff every criterion passes**, otherwise `1` — this is the release gate.

| Criterion | Checks |
|---|---|
| C1 token/latency | hybrid total tokens < raw-docs **and** tokens-per-recall < RAG; latency within 2× RAG |
| C2 deep-latency | KS2 traversal latency still holds on a deterministic depth 4-5 bundle |
| C3 duplicate-rate | re-ingesting the corpus yields ≈0 duplicates |
| C4 fidelity | no edit-drift across ≥20 sequential ingests |
| C5 contradiction-safety | 100% of injected contradictions resolved-or-escalated; 0 silent overwrites |

```bash
uv run kosha bench acceptance --report ACCEPTANCE_REPORT.md
```

### `kosha bench realworld` — Gate-0 v2 re-run

```text
kosha bench realworld [--corpus PATH] [--queries PATH] [--maintenance PATH]
                       [--guidance PATH] [--ingests N] [--seed-concepts N]
                       [--max-queries N] [--fidelity-targeter lexical|generation]
                       [--report PATH] [--json]
```

Run the real-model, held-out benchmark (DEVELOPMENT_PLAN M3 Gate-0 v2): a three-way retrieval comparison, maintenance-routing accuracy, a drift probe across `--ingests` sequential ingests, and the knowledge-integrity safety comparison the reframed kill criterion gates on — the loop's contradiction handling vs a safety-instructed prompt-only baseline. Prints `Gate 0 verdict: GO` or `NO-GO`; with `--report` it also writes the full `ACCEPTANCE_REPORT.md`-shaped document.

| Flag | Default | Description |
|---|---|---|
| `--corpus` | `bundles/pydoc-stdlib` | External corpus bundle. |
| `--queries` | `evals/realworld/queries.jsonl` | Held-out query set. |
| `--maintenance` | `evals/realworld/maintenance.jsonl` | Held-out dedup/novel/contradiction cases. |
| `--guidance` | `consumer/AGENTS.fragment.md` | AGENTS fragment given to the prompt-only baseline. |
| `--ingests` | `50` | Sequential ingests in the drift probe; `50` is the minimum for a valid Gate-0 verdict. |
| `--seed-concepts` | `150` | Corpus concepts seeded into the drift bundle. |
| `--max-queries` | all | Cap the held-out queries evaluated — use this to keep a smoke run fast. |
| `--fidelity-targeter` | `lexical` | Claim targeter used by the edit-drift fidelity probe. |
| `--report` | none | Write the full report to this path. |
| `--json` | off | Print the maintenance/safety/drift comparison as structured JSON instead of the text summary. |

Embedding and generation providers come from the environment (`resolve_embedding_provider`/`resolve_generation_provider`); with none configured, both fall back to the deterministic local providers.

**Offline smoke** — deterministic, no network call, safe to run in CI on every change:

```bash
uv run kosha bench realworld --report ACCEPTANCE_REPORT.md --ingests 5 --max-queries 6
```

**Real-provider Gate-0 v2 re-run** — only a valid recorded verdict once real providers are configured (e.g. `OPENAI_BASE_URL`/`OPENAI_API_KEY` for an OpenAI-compatible endpoint):

```bash
uv run kosha bench realworld --report ACCEPTANCE_REPORT.md --ingests 50
```

Running the `--ingests 50` command *without* configuring real providers still exits `0` (it is a runnable smoke of the same code path) but prints a warning that the result is **not** a valid Gate-0 verdict, so a local-provider run can't be mistaken for the real thing. After a genuine real-provider run, turn the resulting report into the tracked [`docs/gate0-status.md`](gate0-status.md) update with `render_gate_status_summary`/`render_gate_status_row` (`kosha.bench.realworld.status`) rather than hand-editing the verdict prose.

---

## `kosha calibrate`

```text
kosha calibrate [--labels PATH] [--margin FLOAT] [--json]
```

Fit every lexical decision threshold to the configured embedding on the seed labels: the dedup two-threshold band (`--labels`, default `labels/dedup_seed.jsonl`), the adjudicator same/different cutoff (same pairs), the merge claim-targeter cutoff (`labels/merge_seed.jsonl`), and the relator cutoff (`labels/relate_seed.jsonl`). Refuses to run against a held-out `evals/realworld/*` fixture instead of a tracked seed label file.

```bash
uv run kosha calibrate --labels labels/dedup_seed.jsonl
```

---

## `kosha eval`

```text
kosha eval {extract,dedup,merge,relate,contradict} [--labels PATH] [--json] [...]
```

Score one LLM surface against its seed label file. Each surface has its own suite so quality is measured independently. (Running `kosha eval` with no surface exits `2`.)

| Subcommand | Scores | Default labels | Extra flags |
|---|---|---|---|
| `extract` | concept extractor vs granularity labels | `labels/granularity_seed.jsonl` | — |
| `dedup` | dedup precision/recall + repeated-ingest duplicate rate | `labels/dedup_seed.jsonl` | `--bundle` (default `bundles/northwind`) |
| `merge` | merge claim-targeting accuracy | `labels/merge_seed.jsonl` | — |
| `relate` | cross-linker link-discovery precision/recall/F1 | `labels/relate_seed.jsonl` | — |
| `contradict` | contradiction detection precision/recall/F1 | `labels/contradict_seed.jsonl` | — |

All five suites accept `--json` to print their metrics as structured JSON instead of the text summary (`contradict` includes the per-regime breakdown).

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
