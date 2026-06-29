# Kosha Real-Model Acceptance Report (M13, Gate 0)

**Verdict: NO-GO** - the loop does not clear the reframed kill criterion; ship Kosha as an OSS skill and halt M14+.

## Setup

- Corpus: `bundles/pydoc-stdlib` (680 concepts, external)
- Embedding provider: `openai:bge-m3`
- Generation provider: `openai:openai/gpt-4o-mini`
- Held-out queries: 26

## Kill criterion (fixed before the run)

GO only if (1) the loop preserves knowledge integrity under contradiction (conflict detected, prior claim retained, zero silent overwrites) on at least 25% more held-out contradictions than a safety-instructed prompt-only baseline and never silently overwrites, (2) maintenance accuracy does not drop by more than 5% across >=50 ingests that grow the corpus (>=90% add a concept), and (3) edit-drift fidelity holds. Otherwise NO-GO: ship Kosha as an OSS skill and halt M14+.

## Retrieval / answer quality (held-out queries)

| Strategy | Concept recall | Answer-keyword recall | Avg context tokens | Avg total tokens |
|---|---|---|---|---|
| kosha-hybrid | 0.96 | 0.96 | 977 | 1089 |
| tuned-rag | 0.92 | 0.92 | 927 | 1032 |
| prompt-only | 1.00 | 0.96 | 1045 | 1533 |

## Maintenance quality (held-out dedup / novel / contradiction)

| Decider | Accuracy | duplicate | novel | contradiction |
|---|---|---|---|---|
| kosha-loop | 0.50 (12/24) | 0.42 | 1.00 | 0.17 |
| prompt-only | 0.75 (18/24) | 0.58 | 1.00 | 0.83 |

Loop minus prompt-only maintenance accuracy: -0.25 (context only; routing is a structural tie and is not the reframed gate).

## Knowledge-integrity safety under contradiction (the reframed moat)

| Decider | Safe | Safety rate | Silent overwrites |
|---|---|---|---|
| kosha-loop | 6/6 | 1.00 | 0 |
| prompt-only | 6/6 | 1.00 | 0 |

Loop minus prompt-only safety: +0.00 (safety margin 0.25).

## Drift across sequential ingests

- Ingests: 50
- Corpus grew: 80 -> 125 concepts (+45)
- Maintenance accuracy before growth: 0.67
- Maintenance accuracy after growth: 0.62
- Edit-drift fidelity held: True

## Decision

**Verdict: NO-GO.**

Wins:
- maintenance accuracy moved 0.67 -> 0.62 across 50 ingests as the corpus grew +45 (fidelity held: True)

Losses:
- knowledge-integrity safety: loop 1.00 vs prompt-only 1.00 (delta +0.00, margin 0.25); loop silent overwrites 0
- routing decision quality is a structural tie (loop -0.25 vs prompt-only; both call the same LLM) — reported as context, not gated

---

## Post-M13 skill-quality routing re-measurement (spike S1, 2026-06-29)

Spike S1 is a post-M13 engineering spike that makes the OSS maintenance loop *route* well enough to be a good shipped skill. **It does not reopen Gate 0 or unblock M14+ — the verdict stays NO-GO.** It fixes the three mechanical routing faults the M13 per-case diagnostic found, without changing the Gate-0 safety result.

Re-run with the same external corpus and held-out sets, `bge-m3` embedding + `gpt-4o-mini` generation (`kosha bench realworld`):

| Maintenance routing | M13 (before) | S1 (after) | prompt-only |
|---|---|---|---|
| Overall | 0.50 (12/24) | **0.75 (18/24)** | 0.75 (18/24) |
| duplicate | 0.42 | 0.50 | 0.58 |
| novel | 1.00 | 1.00 | 1.00 |
| contradiction | 0.17 | **1.00** | 0.83 |
| loop − prompt-only | −0.25 | **+0.00** | — |

What changed (three fixes):

1. **Multi-candidate adjudication.** The resolver adjudicated only the top-1 neighbor, but `bge-m3` ranks the labeled target #1 only ~half the time (top-6 ~16/18). The adjudicator now selects among the top-k, so a duplicate whose target is ranked 2–6 attaches to the right concept instead of the wrong rank-0 sibling.
2. **Topic-identity routing.** Routing asked "same/duplicate concept?", so a conflicting restatement read as a *different* concept → CREATE and never reached `reconcile()` (contradiction routing 0.17). Routing now asks whether a note updates *or contradicts* an existing concept, so a conflict routes to UPDATE(target) → reconcile (contradiction routing 1.00).
3. **Real-embedding threshold calibration.** `kosha calibrate --labels labels/dedup_seed.jsonl` fits the band to the configured embedding on the seed labels (`bge-m3`: high 0.936 / low 0.620, fit on the seed set only — the held-out maintenance set is never used), and the benchmark warns when the lexical-tuned `DEFAULT_THRESHOLDS` are used with a real embedding. The exact-re-ingest duplicate rate stays ~0 (a re-embed self-matches at cosine 1.0, above the fitted-or-default `high`).

Unchanged — the Gate-0 result stands:

- **Knowledge-integrity safety is still a tie: loop 1.00 vs prompt-only 1.00.** Routing reached *parity* (loop = prompt-only = 0.75), not a win — the loop's adjudicator and the prompt call the same LLM, so decision quality converges. Edit-drift fidelity held (0.79 → 0.79 across 50 ingests, 150 → 187 concepts).
- **Verdict: NO-GO.** Kosha ships as an OSS skill; M14+ remains halted. S1 improves the shipped skill's routing; it does not make the loop beat a prompt.

Generation is non-deterministic at the provider's default temperature, so the held-out routing oscillates a few points run-to-run (~0.71–0.79); the loop-vs-prompt-only gap is read from a single run for an apples-to-apples comparison.
