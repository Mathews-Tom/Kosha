# Docs-impact policy for agent-authored prose

Kosha's generated public surfaces are deterministic by default. Future extensions may propose agent-authored documentation prose, but that path must stay secondary to `kosha sync` renderers and must be reviewable before any write.

This policy is a gate for non-deterministic documentation changes. It does not authorize a model to rewrite docs broadly, approve bundle changes, or change public product claims without evidence.

## Required impact plan

Before any agent-authored docs edit, write a short impact plan with one row per proposed edit:

| Source change | Affected document | Required edit | Evidence | Mode |
|---|---|---|---|---|
| Source file, report, CLI surface, or bundle artifact that changed | Exact Markdown file and section | Narrow sentence, row, or section change | Checked-in artifact, command output, report path, or source line | `deterministic` or `agent-authored` |

Every row must satisfy this chain:

```text
source change -> affected document -> required edit -> evidence -> deterministic or agent-authored
```

A reviewer must be able to trace each prose change back to the cited source without trusting the model's summary.

## Allowed changes

- Narrow edits that keep docs synchronized with a changed command, report, renderer, or checked-in artifact.
- Agent-authored explanatory prose that is explicitly grounded in source files or recorded reports.
- Deterministic sync output produced by `kosha sync docs` or `kosha sync status`.
- Clarifications that reduce overclaim risk, especially around real-model Gate-0, traversal boundaries, and provider configuration.

## Blocked changes

- Broad rewrites that are not tied to specific source changes.
- Formatting-only edits.
- Public claims without source evidence.
- Generated claims about real-model quality unless backed by a checked-in recorded report.
- Claims that M14+ product expansion is unhalted without a new recorded GO decision.
- Claims that host sessions with generic filesystem tools are sandboxed by Kosha today.
- Any workflow or doc path that runs `kosha ingest --yes`, stages bundle files from scheduled sync, or approves BLOCK-lane knowledge changes.

## Required checks

Run the narrowest command that covers the changed docs first, then the repo gate before merge:

```bash
uv run pytest tests/docs/test_sync_docs.py tests/docs/test_public_claims.py -q
uv run kosha sync check
uv run kosha doctor providers
uv run ruff check
uv run mypy --strict src
uv run pytest -q
uv run kosha validate tests/fixtures/good_bundle
```

`kosha doctor providers` output may be pasted into reviews only after confirming secret values are redacted.

## Temporary-plan hygiene

The impact plan is a review aid, not a shipped artifact, unless the PR explicitly adds this policy or a reusable template. Delete temporary plan files before final output. Keep the durable evidence in the PR body, commit body, test names, or source document references.

## Review checklist

- Each docs edit maps to a source change, affected document, required edit, evidence, and mode.
- Agent-authored rows are narrow and cite checked-in evidence.
- Deterministic rows match `kosha sync` output or a source-backed manual equivalent.
- No broad rewrites or formatting-only edits are mixed into the change.
- Public real-model claims are backed by recorded reports.
- Workflow examples do not mutate bundles or approve BLOCK-lane changes.
- `tests/docs/test_sync_docs.py` and `tests/docs/test_public_claims.py` pass.
