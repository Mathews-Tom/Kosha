# Contributing

Kosha is a deterministic spine with isolated, eval-gated LLM surfaces. Contributions are expected to keep that shape: code owns control flow, file I/O, conformance, and traversal; the model is touched only behind a typed provider interface with an eval suite. Read [system design §1](docs/system_design.md) before changing the architecture.

## Development setup

Requires Python ≥ 3.12 and [`uv`](https://docs.astral.sh/uv/).

```bash
git clone <repo-url> kosha && cd kosha
uv sync           # runtime + dev toolchain (ruff, mypy, pytest, mcp)
uv run kosha --version
```

Use `uv` only — never `pip`. Add dependencies with `uv add` (or `uv add --dev` for tooling).

## The gate set

CI runs these on every push and pull request ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)). Run them locally before opening a PR — they are the contract:

```bash
uv run ruff check                              # lint
uv run mypy --strict src                       # type-check (strict)
uv run pytest -q                               # tests
uv run kosha validate tests/fixtures/good_bundle   # conformance gate
```

All four must pass. The acceptance gate and per-surface eval suites run separately (and may make model calls when a non-local provider is configured), so they are opt-in via the manual `Acceptance` workflow:

```bash
uv run kosha bench acceptance --report ACCEPTANCE_REPORT.md
uv run pytest evals -q
```

## Code style

Enforced by `ruff` and `mypy --strict` (config in [`pyproject.toml`](pyproject.toml)):

- Line length 100, target `py312`.
- Lint rule sets: `E`, `F`, `I`, `UP`, `B`, `SIM`, `RUF`.
- `from __future__ import annotations` at the top of every module.
- Built-in generics and `|` unions; no `typing.Any` in generics. Full strict typing — no untyped defs, no implicit `Any`.
- Pydantic models for every typed boundary.

No silent failures: fail loud rather than falling back. A half-configured provider should error, not degrade to a default (see [configuration](docs/configuration.md)). No `try/except ImportError`, no placeholder/mock values in shipped code.

## Tests

`tests/` mirrors the source tree — one directory per subsystem (`okf/`, `dedup/`, `merge/`, `contradiction/`, `link/`, `indexlog/`, `pipeline/`, `mcp/`, `providers/`, `index/`, `bench/`, `validate/`). `evals/` holds the per-LLM-surface eval gates scored against the seed labels in `labels/`.

When adding behavior:

- Add tests next to the subsystem you changed; assert observable behavior and invariants (round-trip stability, no edit-drift, no silent overwrite), not incidental defaults.
- Touching an LLM surface (extract, dedup, merge, relate, contradict) means updating its eval suite under `evals/` and, where relevant, the seed labels.
- Changing the on-disk format means updating the conformance/round-trip tests under `tests/okf` and `tests/validate`.
- Keep the default providers deterministic so the suite stays offline and reproducible.

`pytest` discovers both `tests` and `evals` (`testpaths` in `pyproject.toml`).

## Commits and pull requests

Follow [Conventional Commits 1.0.0](https://www.conventionalcommits.org/):

```text
<type>[optional scope]: <description>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`. Subject in imperative mood, lowercase, no trailing period, ≤72 chars. Breaking changes use `!` and/or a `BREAKING CHANGE:` footer.

- One logical change per commit.
- PR titles are valid Conventional Commit subjects (squash-merge uses them as the commit message).
- PR body: what and why; call out breaking changes; link issues with `Closes #N` / `Refs #N`.
- The PR must pass the full gate set above before review.

## Non-negotiables

- The artifact stays open and self-sufficient: output is plain OKF files; no proprietary store on the critical path.
- Every write goes through the plan → approve → commit gate; no silent mutation of a bundle.
- Conformance is a gate, not a guideline: non-conformant output never reaches `main`.
- Model- and cloud-neutral: no dependency on a specific model, cloud, or agent framework outside the provider layer.
