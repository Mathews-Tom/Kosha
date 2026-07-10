# Experiments and Reproducibility

This section presents every experiment behind the paper's claims, in the order they were run, and separates deterministic offline reproduction from paid real-provider reproduction. Every number below is linked to a checked-in report in `.docs/paper/evidence-ledger.md`.

## A. Deterministic self-consistency appendix

Before any real-model claim, the pipeline mechanics are verified offline against `bundles/northwind` (12 concepts) with the deterministic local providers (`lexical-hash-256` embeddings, `extractive-3` generation). This appendix is a self-consistency check on toy providers, not a real-RAG or real-model comparison, and is presented at that reduced altitude throughout this package.

| Criterion | Result |
|---|---|
| Hybrid tokens-per-recall vs. RAG (matched quality) | hybrid 602 vs RAG 865 tokens-per-recall; hybrid 602 vs raw-docs 1131 total tokens |
| Duplicate rate on re-ingest | 0.000 (0 CREATE / 12 UPDATE) |
| Edit-drift fidelity, lexical targeter | held across 20 sequential ingests |
| Injected contradiction handling | 12/12 detected and resolved-or-escalated, 0 silent overwrites |

Zero silent overwrite is verified as a design invariant of `reconcile()` (`src/kosha/contradiction/escalate.py`), stated once here rather than repeated as an empirical finding across every report: the writer is structurally built to append or status-flip, so the invariant holds by construction and is an integration-boundary regression guard, not a result that generalizes claims about decision quality.

**Reproduction (deterministic):**

```bash
uv run kosha bench acceptance --report ACCEPTANCE_REPORT.md
```

## B. Real-model Gate-0: single corpus, single vendor family (M13/S2)

The maintenance loop (embedding routing plus reserved LLM adjudication) was compared against a well-instructed prompt-only baseline across three pre-registered runs on `bundles/pydoc-stdlib` (680 concepts), all before the second-corpus generalization experiment in section C:

| Run | Setup | Result |
|---|---|---|
| M13 Gate-0 | bge-m3 + gpt-4o-mini, 50 sequential ingests | real-model NO-GO — maintenance accuracy 0.50 vs prompt-only 0.79; contradiction routing 0.17 vs 1.00 |
| M13-reframed | same corpus/provider, safety-margin criterion | real-model NO-GO — safety tied 1.00 vs 1.00, below the required +0.25 margin |
| S2 Gate-0 v2 | 2 embeddings x 2 generation models x 3 runs, 108 held-out contradictions across 6 regimes | real-model NO-GO — loop trails prompt-only by 0.28-0.33 on detection and safety across all 8 provider cells; 12-case llama-3.3-70b smoke corroborates the same pattern |

The pre-registered kill criterion required a >=15% median margin over prompt-only, noise-band excluded, on every provider cell, plus zero silent overwrites. No cell cleared it on any of the three runs. Full setup and per-cell numbers are in `docs/gate0-status.md`.

## C. S2-v3: second corpus, cross-vendor powered replication (M3)

The single-corpus, single-vendor caveat from section B is the hard generalization blocker this experiment closes. `bundles/paper-s2v3-corpus` (NASA Apollo Flight Journal transcripts, public domain, 2 concepts) was selected as a non-Python-docs domain (`bundles/paper-s2v3-corpus/MANIFEST.md`), with held-out query and maintenance fixtures and pre-registered criteria (`.docs/s2-v3-preregistration.md`) frozen before any powered run.

**Setup:** `openai:bge-m3` embeddings (local OpenAI-compatible endpoint) plus two OpenRouter generation models from different vendors — `openai/gpt-4.1-nano` and `qwen/qwen3-235b-a22b-2507` — 50 sequential ingests per cell.

**Result: NO-GO on both cells.** The OpenAI cell preserved maintenance accuracy across the 50-ingest drift path (1.00 -> 1.00); the Qwen cell regressed (1.00 -> 0.00). Neither cell supports a decision-quality or retrieval-superiority claim. The held-out sample is thin — 1 query and 0 contradiction cases per cell — so the safety axis reflects an empty sample rather than a measured loss; this is disclosed as a limitation, not smoothed over.

The negative result generalizes: a second, non-Python-docs corpus with a cross-vendor generation matrix reproduces the same qualitative outcome as the single-corpus S2 run in section B. This is why the paper is framed around a generalized negative finding rather than pivoting to a conditional-autonomy story (see the draft's conclusion for the decision rule that would have triggered that pivot).

**Reproduction:**

```bash
# deterministic smoke (not a valid Gate-0 verdict)
uv run kosha bench realworld --corpus bundles/paper-s2v3-corpus \
  --queries evals/paper_s2v3/queries.jsonl \
  --maintenance evals/paper_s2v3/maintenance.jsonl \
  --ingests 5 --max-queries 6 --report /tmp/kosha-s2v3-smoke.md

# real-provider (reviewed env; see docs/configuration.md)
uv run kosha doctor providers
uv run kosha bench realworld --corpus bundles/paper-s2v3-corpus \
  --queries evals/paper_s2v3/queries.jsonl \
  --maintenance evals/paper_s2v3/maintenance.jsonl \
  --ingests 50 --report .docs/s2-v3-report.md
```

## D. Real-model fidelity: generation-targeter drift probe (M4)

Every fidelity result up to and including section C used the deterministic `LexicalClaimTargeter` inside the edit-drift probe — exact by construction on its own synthetic supersede loop, and not itself evidence that a real model preserves the same guarantee. This experiment swaps in `GenerationClaimTargeter`, which prompts a real generation provider to choose which in-force claim a new statement revises.

**Setup:** same embedding/generation providers as section C's OpenAI cell (`openai:bge-m3` + `openai:openai/gpt-4.1-nano`), `--fidelity-targeter generation`, 50 sequential ingests.

**Result: edit-drift fidelity did NOT hold** — `fidelity_targeter: generation:openai:openai/gpt-4.1-nano`, `fidelity_ok: False`, versus `fidelity_ok: True` under the lexical targeter on every prior report. This is reported as an honest additional negative finding: the governance mechanism's edit-drift guarantee, as currently implemented, depends on the deterministic targeter and is not yet demonstrated to hold when an LLM performs the claim-targeting judgment. Full detail is in `.docs/real-model-fidelity-report.md` and `.docs/paper-positioning.md` section 4.

**Reproduction:**

```bash
# deterministic smoke
uv run kosha bench realworld --corpus bundles/paper-s2v3-corpus \
  --queries evals/paper_s2v3/queries.jsonl \
  --maintenance evals/paper_s2v3/maintenance.jsonl \
  --ingests 5 --max-queries 6 --fidelity-targeter generation \
  --report /tmp/kosha-fidelity-smoke.md

# real-provider (reviewed env)
uv run kosha bench realworld --corpus bundles/paper-s2v3-corpus \
  --queries evals/paper_s2v3/queries.jsonl \
  --maintenance evals/paper_s2v3/maintenance.jsonl \
  --ingests 50 --fidelity-targeter generation \
  --report .docs/real-model-fidelity-report.md
```

## E. Reproducibility instructions

Two reproduction tiers exist throughout this package, and every command above is labeled with one:

- **Deterministic** — the default local providers (`lexical-hash-256`, `extractive-3`) make every command byte-reproducible offline, with no network calls and no cost. `uv run pytest -q`, `uv run kosha bench acceptance`, and every `--ingests <=6` smoke command in this document fall in this tier and are exercised in CI on every PR.
- **Real-provider (approximate)** — sections C and D require reviewed `KOSHA_EMBED_*`/`KOSHA_GEN_*` environment configuration (see `docs/configuration.md`, `.env.example`) and paid API access. Provider identities, redacted diagnostics, and run parameters are recorded in the checked-in report for each run. A third party can reproduce the *qualitative* verdict (NO-GO on every axis measured) but not the exact numbers: real-model outputs carry run-to-run variance, and this package does not claim exact reproducibility of paid-model results.

## F. Limitations

- **S2-v3 held-out sample size.** 1 held-out query and 0 contradiction cases per cell is a thin sample; the 0.00 safety rate on the Qwen cell reflects an empty sample, not a measured safety loss, and the paper does not overstate it as one.
- **Generation-targeter fidelity is a single real-provider run.** The M4 result uses one generation model (`openai/gpt-4.1-nano`); it is not yet a cross-vendor matrix in the way section C's decision-quality experiment is.
- **Real-model run-to-run variance.** Paid-model outputs are not exactly reproducible; only the qualitative verdict is expected to reproduce.
- **No production behavior is authorized by any experiment in this document.** M14+ product expansion stays halted regardless of outcome; see `docs/gate0-status.md` for the current public verdict.
