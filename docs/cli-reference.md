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
kosha ingest <source> [--bundle PATH] [--dry-run] [--yes | --review] [--authority N] [--json]
```

Run the full maintenance loop on a source folder behind the **plan → approve → commit** gate: extract concepts → dedup-resolve against the bundle → merge through the claim layer → cross-link → detect contradictions → regenerate `index.md` / append `log.md` → assemble a change plan → route by graduated autonomy → write and commit on approval.

| Flag | Default | Description |
|---|---|---|
| `source` | — | Source folder (Markdown) to ingest. |
| `--bundle` | `bundles/northwind` | Target OKF bundle directory. |
| `--dry-run` | off | Build and print the plan; write nothing, commit nothing. |
| `--yes` | off | Approve the whole plan non-interactively (explicit human approval for the block lane). Mutually exclusive with `--review`. |
| `--authority` | `0` | Source authority rank for contradiction resolution; higher wins, ties escalate. |
| `--review` | off | Approve or reject each proposed change individually instead of one blanket yes/no. An escalated conflict must be acknowledged before any change commits; rejecting one withholds the whole plan. Mutually exclusive with `--yes`. |
| `--json` | off | Print the plan/routing/commit outcome as structured JSON instead of the text report. File content is never included; under `--review`, also includes each item's `approve`/`reject` decision. |

**Approval semantics.** Auto- and skim-lane plans apply under delegated autonomy. A blocked plan (contradiction, deletion/supersede of a load-bearing claim, or low-confidence dedup) requires an explicit yes: pass `--yes`, answer the interactive prompt, or — with neither — the plan is rejected default-safe (nothing is written). `--review` replaces the single yes/no with one prompt per proposed change (and per escalated conflict); without an interactive terminal to answer from, every item defaults to rejected — the same default-safe outcome as the blanket gate.

```bash
# Preview only
uv run kosha ingest ./updates --bundle bundles/northwind --dry-run

# Apply, treating the source as higher-authority than the wiki
uv run kosha ingest ./policy-docs --bundle bundles/northwind --authority 2 --yes

# Approve or reject each proposed change one at a time
uv run kosha ingest ./policy-docs --bundle bundles/northwind --review
```

### Supported source adapter formats

The `kosha ingest` CLI ingests a local Markdown source folder directly. Additional adapters are library APIs under `kosha.ingest`; they normalize local export files into `RawDoc` values that can be passed to the pipeline's `raw_docs` parameter. They do not call live SaaS APIs, accept credentials, or fetch remote export links.

| Adapter | Function | Supported input | Provenance |
|---|---|---|---|
| Markdown folder | `kosha.ingest.ingest_folder(root)` | Directory tree of UTF-8 `*.md` files. Files are read in sorted path order. | `source_id` and `location` are the POSIX path relative to `root`; `kind` is `markdown`. |
| Confluence export | `kosha.ingest.ingest_confluence_export(root)` | Local directory containing UTF-8 `*.md` files and/or `*.json` page files. JSON may be one page object or a list of page objects. Each page object must contain string `id`, string `title`, and string `body` or `content`. | Markdown pages use `confluence:<relative-path>`; JSON pages use `confluence:<id>` with `location` `<relative-json-path>#<id>`; `kind` is `workspace_export`. |
| Notion export | `kosha.ingest.ingest_notion_export(root)` | Local directory tree of UTF-8 `*.md` files from a Notion-style Markdown export. | `source_id` is `notion:<relative-path>`; `location` is the relative path; `kind` is `workspace_export`. |
| Slack export | `kosha.ingest.ingest_slack_export(root)` | Local Slack-style JSON export directory. Each `*.json` file must be a non-empty array of message objects with string `ts` and `text`; string `user` is optional. | `source_id` is `slack:<channel>/<date>` for nested channel/day files; `location` is the relative JSON path; `kind` is `workspace_export`. |
| PDF/DOCX documents | `kosha.ingest.documents.ingest_documents(path)` | One `.pdf`/`.docx` file or a directory tree of those files. Requires the explicit optional extra: `uv sync --extra documents`. Unsupported extensions are rejected. | `source_id` is `document:<filename>` for one file or `document:<relative-path>` for a directory; `location` is the filename or relative path; `kind` is `document`. |

Every adapter applies the shared ingest policy before yielding `RawDoc`: bounded bytes via `IngestPolicy(max_bytes=...)`, hidden-Unicode prompt-injection sanitization, and stable `Source` metadata. URL sources additionally keep the M6 network guardrails: only HTTP(S), public resolved addresses, and bounded response bytes. Secret-like content is scanned later when the pipeline builds file changes; a matching detector routes the change to the BLOCK lane rather than auto-committing it.

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

## `kosha recover`

```text
kosha recover backups <bundle> [--json]
kosha recover restore <bundle> --tag TAG [--apply] [--branch NAME] [--audit-log PATH] [--json]
kosha recover reindex <bundle> [--apply] [--branch NAME] [--audit-log PATH] [--json]
```

Operator recovery over the existing safety substrates: `backups` lists every `backup/<date>` tag `ingest` leaves behind; `restore` brings the bundle back to a backup tag's recorded state; `reindex` regenerates any `index.md` files that drifted from the bundle's actual concepts. All three take a bundle that is itself a Git repository.

**Safety contract.** `restore` and `reindex` show the exact refs/files an action would touch (`describe_*`) without writing anything by default; only `--apply` mutates. Every mutation writes on its own branch — never `main` directly — and takes a fresh, uniquely-timestamped `recovery-safety/<timestamp>` tag *before* touching anything, so the pre-recovery state is always one tag away, never silently lost. `restore` additionally re-verifies the target `--tag` exists immediately before mutating (verify-then-act, not trust-then-act).

| Flag | Default | Description |
|---|---|---|
| `bundle` | — | Path to the OKF bundle directory (a Git repository). |
| `--tag` | — | (`restore` only, required) Backup tag to restore to, e.g. `backup/2026-07-01`. |
| `--apply` | off | Actually perform the mutation. Default is dry-run: show the plan only. |
| `--branch` | auto-named | Branch to commit on. |
| `--audit-log` | none | Append the `RecoveryRecord` audit record to this JSONL file. |
| `--json` | off | Print the plan/record as structured JSON instead of text. |

```bash
# See what backup tags exist
uv run kosha recover backups bundles/northwind

# Preview a restore — shows exact files/refs, writes nothing
uv run kosha recover restore bundles/northwind --tag backup/2026-07-01

# Apply it, with a durable audit trail
uv run kosha recover restore bundles/northwind --tag backup/2026-07-01 --apply --audit-log recovery-audit.jsonl

# Fix drifted index.md files after a hand-edit
uv run kosha recover reindex bundles/northwind --apply
```

---

## `kosha release`

```text
kosha release <bundle> --tag VERSION [--out PATH] [--json]
```

Tag the bundle's current committed state (`HEAD`) as an immutable release. Refuses (exit `1`) when the bundle has OKF conformance errors, or when `--tag`'s release already exists — releases never move once cut, unlike the ingest pipeline's force-moving daily `backup/<date>` tag. The tag is `release/<VERSION>`; with `--out`, a content-addressed archive (`.zip` or `.tar`) of that exact tree is also written, so exporting the same commit twice under different tag names produces byte-identical archives.

| Flag | Default | Description |
|---|---|---|
| `bundle` | — | Path to the OKF bundle directory (a Git repository). |
| `--tag` | — | Required. Release version, e.g. `v1` (tagged as `release/v1`). |
| `--out` | none | Export a content-addressed archive (`.zip` or `.tar`) to this path. |
| `--json` | off | Print the release record as structured JSON instead of text. |

```bash
uv run kosha release bundles/northwind --tag v1
uv run kosha release bundles/northwind --tag v2 --out dist/northwind-v2.zip
```

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
| `2` | `recover` — unknown backup tag, not a bundle directory, or not a Git repository |
| `1` | `release` — bundle not conformant, or the release tag already exists |
