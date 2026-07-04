# CI integration

Kosha ships a packaged GitHub Action that runs `kosha validate` against a bundle path in a consumer repository — the same conformance gate Kosha's own CI runs on every push (`.github/workflows/ci.yml`), packaged for repos that only store an OKF bundle and don't otherwise depend on Kosha.

## `Mathews-Tom/Kosha` (validate-on-PR)

```yaml
name: Validate knowledge bundle

on:
  pull_request:
    paths:
      - "knowledge/**"

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: Mathews-Tom/Kosha@v0.1.0
        with:
          bundle-path: knowledge
```

| Input | Required | Default | Description |
|---|---|---|---|
| `bundle-path` | yes | — | Path to the OKF bundle directory to validate, relative to the repository root. |
| `version` | no | latest published release | Pin a specific `kosha-okf` PyPI version instead of installing whatever is newest. |
| `extra-args` | no | (empty) | Extra arguments forwarded to `kosha validate`, e.g. `--json` on a version that supports it ([CLI reference](cli-reference.md#kosha-validate)). |

The action installs `kosha-okf` from PyPI via `uvx` — it does not need Python or `uv` set up beforehand, and it runs in its own ephemeral environment isolated from the rest of the job. `kosha validate`'s exit code gates the job: `0` when the bundle has no error-severity findings (warnings are allowed), non-zero otherwise ([exit codes](cli-reference.md#exit-codes)).

Pin `uses:` to a released tag (not `@main`) for a stable, reproducible check.

## Self-test

`.github/workflows/action-smoke.yml` exercises the action against Kosha's own conformant and non-conformant fixtures (`tests/fixtures/good_bundle`, `tests/fixtures/bad_bundle`) on every push, so a regression in the action itself fails CI the same way a source regression would.

## Running the same check without the Action

Any CI system that can run a container or install `uv` can call the CLI directly:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uvx kosha-okf kosha validate knowledge
```
