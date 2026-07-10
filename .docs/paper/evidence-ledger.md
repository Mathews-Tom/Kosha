# Evidence Ledger

Every numeric claim used in the Kosha paper package links to a checked-in report or a reproducible command. This ledger is the single source of truth for that mapping; `tests/docs/test_paper_claims.py` parses the `Source` column of the table below and fails the build if a cited path does not exist in the repository, so the ledger cannot silently drift from the evidence it claims to cite.

Reproduction commands assume `uv run` from the repository root. Commands prefixed `[deterministic]` reproduce byte-for-byte offline with the default local providers. Commands prefixed `[real-provider]` require reviewed `KOSHA_EMBED_*`/`KOSHA_GEN_*` environment configuration and paid API access; their reports are checked in, but the exact numbers carry run-to-run model variance (see `docs/configuration.md` and the reproducibility section of this package).

## Deterministic self-consistency evidence

| Claim | Value | Source |
|---|---|---|
| Hybrid tokens-per-recall vs. RAG | hybrid 602 vs RAG 865 | `ACCEPTANCE_REPORT.md` |
| Hybrid vs. raw-docs token cost | hybrid 602 vs raw-docs 1131 | `ACCEPTANCE_REPORT.md` |
| Duplicate rate on re-ingest | 0.000 (0 CREATE / 12 UPDATE) | `ACCEPTANCE_REPORT.md` |
| Edit-drift fidelity, lexical targeter | held across 20 sequential ingests | `ACCEPTANCE_REPORT.md` |
| Injected contradictions handled | 12/12 detected and resolved-or-escalated, 0 silent overwrites | `ACCEPTANCE_REPORT.md` |

Reproduction: `[deterministic] uv run kosha bench acceptance --report ACCEPTANCE_REPORT.md`.

## Real-model Gate-0 evidence (decision-quality, single corpus)

| Claim | Value | Source |
|---|---|---|
| M13 Gate-0 maintenance accuracy | loop 0.50 vs prompt-only 0.79 | `docs/gate0-status.md` |
| M13 Gate-0 contradiction routing | loop 0.17 vs prompt-only 1.00 | `docs/gate0-status.md` |
| M13-reframed safety-margin tie | loop 1.00 vs prompt-only 1.00 (needed +0.25 margin) | `docs/gate0-status.md` |
| S2 Gate-0 v2 provider-matrix trail | loop trails prompt-only by 0.28-0.33 on detection and safety across 8 provider cells | `docs/gate0-status.md` |
| S2 Gate-0 v2 held-out sample | 108 held-out contradictions across 6 regimes, 2 embeddings x 2 generation models x 3 runs | `docs/gate0-status.md` |
| S2 cross-vendor smoke corroboration | llama-3.3-70b cross-vendor smoke shows the same trailing pattern | `docs/gate0-status.md` |

Reproduction: real-provider results require reviewed provider env; see `docs/gate0-status.md` for the full evidence table and current public verdict.

## S2-v3 second-corpus, cross-vendor evidence (M3)

| Claim | Value | Source |
|---|---|---|
| S2-v3 provider-matrix verdict | NO-GO on both generation-provider cells | `.docs/s2-v3-report.md` |
| S2-v3 OpenAI cell maintenance accuracy across drift | 1.00 -> 1.00 across 50 ingests | `.docs/s2-v3-report.md` |
| S2-v3 Qwen cell maintenance accuracy across drift | 1.00 -> 0.00 across 50 ingests | `.docs/s2-v3-report.md` |
| S2-v3 held-out sample size caveat | 1 held-out query, 0 contradiction cases per cell | `.docs/s2-v3-report.md` |

Reproduction: `[deterministic] uv run kosha bench realworld --corpus bundles/paper-s2v3-corpus --queries evals/paper_s2v3/queries.jsonl --maintenance evals/paper_s2v3/maintenance.jsonl --ingests 5 --max-queries 6 --report /tmp/kosha-s2v3-smoke.md` (smoke only, not a valid Gate-0 verdict). `[real-provider]` full command and provider identities are recorded in `.docs/s2-v3-report.md` and `.docs/s2-v3-preregistration.md`.

## Real-model fidelity evidence (M4)

| Claim | Value | Source |
|---|---|---|
| Fidelity under lexical targeter (exact by construction) | `fidelity_ok: True` on every prior report | `.docs/s2-v3-report.md` |
| Fidelity under real generation-model targeter | `fidelity_ok: False`, `fidelity_targeter: generation:openai:openai/gpt-4.1-nano`, 50 sequential ingests | `.docs/real-model-fidelity-report.md` |

Reproduction: `[deterministic] uv run kosha bench realworld --corpus bundles/paper-s2v3-corpus --queries evals/paper_s2v3/queries.jsonl --maintenance evals/paper_s2v3/maintenance.jsonl --ingests 5 --max-queries 6 --fidelity-targeter generation --report /tmp/kosha-fidelity-smoke.md` (smoke only). `[real-provider]` full command is recorded in `.docs/real-model-fidelity-report.md`.

## Repository scale claims

| Claim | Value | Source |
|---|---|---|
| CI-gated checks | `ruff`, `mypy --strict`, `pytest`, `kosha validate` | `.github/workflows/ci.yml` |

Every claim above is either a byte-reproducible deterministic command or a checked-in real-provider report; none is asserted from memory or an unreproducible run.
