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
