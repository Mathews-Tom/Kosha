# Kosha Sync operations guide

Kosha Sync keeps checked-in public surfaces aligned with deterministic sources of truth in the repository. It is an operator convenience for documentation generated from code, recorded benchmark reports, and traversal fallback renderers. It is not an ingest workflow and it does not change an OKF bundle.

Use this guide when deciding whether a maintenance task belongs in `kosha sync`, `kosha validate`, `kosha ingest`, `kosha serve`, or `kosha doctor providers`.

## Command boundary

| Command | Use when | Writes? | Source of truth |
|---|---|---:|---|
| `kosha sync check` | CI or local pre-PR verification needs to confirm generated public surfaces still match code and recorded reports. | No | CLI parser, recorded Gate-0 report, fallback renderer, public-claim scanner |
| `kosha sync docs` | A code change modifies generated documentation sections such as the CLI command table, MCP tool table, or traversal fallback artifacts. | Generated public docs and consumer fallback files only | `src/kosha/cli.py`, `src/kosha/mcp/`, `src/kosha/sync/` |
| `kosha sync status` | A checked-in benchmark/status source changes and the public status table or Gate-0 summary must be refreshed. | Generated status sections only | `ACCEPTANCE_REPORT.md`, recorded Gate-0 report helpers |
| `kosha sync agent-fragment` | An operator wants to install or refresh the traversal instructions in a specific `AGENTS.md` or `CLAUDE.md` file. | Only the bounded Kosha fragment in the selected file | `kosha.mcp.fallback` renderer |
| `kosha validate` | An OKF bundle must be checked for conformance before merge, release, or handoff. | No | The bundle files passed on the command line |
| `kosha ingest` | New source material needs to become reviewed bundle changes through the plan → approve → commit gate. | Bundle changes on an ingest branch after approval | Source documents and the target bundle |
| `kosha serve` | A bundle should be served over the local traversal-only HTTP/SSE boundary. | No | The configured bundle path |
| `kosha doctor providers` | An operator needs to inspect provider configuration and redacted environment diagnostics. | No | Provider environment variables and local defaults |

## Routine generated-surface sync

Run the read-only checker first:

```bash
uv run kosha sync check
```

If it reports drift in generated public surfaces, run the deterministic writers for the affected surface class:

```bash
uv run kosha sync docs
uv run kosha sync status
uv run kosha sync check
```

Review the diff before committing. Expected writable paths are limited to generated sections in:

- `README.md`
- `docs/cli-reference.md`
- `docs/gate0-status.md`
- `docs/mcp-integration.md`
- `consumer/AGENTS.fragment.md`
- `consumer/kosha-traversal/SKILL.md`
- `.kosha/sync-state.json`

Do not use `sync` to edit concepts, `index.md`, `log.md`, or other bundle files. Bundle maintenance belongs to `kosha ingest`, followed by review and validation.

## Scheduled PR workflow

Use [`docs/examples/kosha-sync-pr.yml`](examples/kosha-sync-pr.yml) as the copyable GitHub Actions example. It is inert while it stays under `docs/examples/`. To enable it in a maintained repository, copy it to `.github/workflows/kosha-sync-pr.yml` and review its `add-paths` list for that repository's generated surfaces.

The example runs:

```bash
uv run kosha sync docs
uv run kosha sync status
uv run kosha sync check
uv run kosha doctor providers
```

It opens a pull request for generated public surfaces only. It does not run `kosha ingest`, does not pass `--yes`, does not stage bundle paths, and does not approve BLOCK-lane knowledge changes.

## When not to use sync

- Use `kosha validate` for bundle conformance gates; `sync check` does not validate a bundle.
- Use `kosha ingest --dry-run` to preview knowledge maintenance plans; `sync docs` and `sync status` do not extract, deduplicate, merge, link, or contradict source material.
- Use `kosha ingest` with explicit approval for reviewed bundle writes; scheduled sync workflows must not approve BLOCK-lane changes.
- Use `kosha serve` or `kosha-mcp` to expose traversal tools to agents; sync does not start a server.
- Use `kosha doctor providers` before provider-sensitive runs; sync does not hide or repair half-configured providers.

## Public-claim boundary

Generated status text must stay tied to recorded reports. Do not add new public claims about real-model quality, provider performance, or traversal guarantees unless a checked-in source artifact backs the claim and `kosha sync check` plus `tests/docs/test_public_claims.py` pass.

The current public product boundary remains: deterministic mechanics are verified locally, real-model Gate-0 recorded a NO-GO, M14+ product expansion remains halted, and host sessions with generic filesystem tools are not sandboxed by Kosha today.

Future agent-authored prose changes must follow the source-change → doc → edit → evidence mapping in [Docs-impact policy](docs-impact-policy.md) before any write.
