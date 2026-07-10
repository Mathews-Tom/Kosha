# Kosha Real-Model Acceptance Report (M13, Gate 0)

**Verdict: NO-GO** - the loop does not clear the reframed kill criterion; ship Kosha as an OSS skill and halt M14+.

## Setup

- Corpus: `bundles/paper-s2v3-corpus` (2 concepts, external)
- Embedding provider: `openai:bge-m3` (env: KOSHA_EMBED_BASE_URL=http://localhost:11434/v1, KOSHA_EMBED_MODEL=bge-m3, KOSHA_EMBED_API_KEY=unus..., KOSHA_EMBED_DIM=1024)
- Generation provider: `openai:openai/gpt-4.1-nano` (env: KOSHA_GEN_BASE_URL=https://openrouter.ai/api/v1, KOSHA_GEN_MODEL=openai/gpt-4.1-nano, KOSHA_GEN_API_KEY=sk-or-v...4817)
- Held-out queries: 1

## Kill criterion (fixed before the run)

GO only if (1) the loop preserves knowledge integrity under contradiction (conflict detected, prior claim retained, zero silent overwrites) on at least 25% more held-out contradictions than a safety-instructed prompt-only baseline and never silently overwrites, (2) maintenance accuracy does not drop by more than 5% across >=50 ingests that grow the corpus (>=90% add a concept), and (3) edit-drift fidelity holds. Otherwise NO-GO: ship Kosha as an OSS skill and halt M14+.

## Retrieval / answer quality (held-out queries)

| Strategy | Concept recall | Answer-keyword recall | Avg context tokens | Avg total tokens |
|---|---|---|---|---|
| kosha-hybrid | 1.00 | 1.00 | 235 | 266 |
| tuned-rag | 1.00 | 1.00 | 235 | 256 |
| prompt-only | 1.00 | 1.00 | 247 | 687 |

## Maintenance quality (held-out dedup / novel / contradiction)

| Decider | Accuracy | duplicate | novel | contradiction |
|---|---|---|---|---|
| kosha-loop | 1.00 (1/1) | 0.00 | 1.00 | 0.00 |
| prompt-only | 1.00 (1/1) | 0.00 | 1.00 | 0.00 |

Loop minus prompt-only maintenance accuracy: +0.00 (context only; routing is a structural tie and is not the reframed gate).

## Knowledge-integrity safety under contradiction (the reframed moat)

| Decider | Safe | Safety rate | Silent overwrites |
|---|---|---|---|
| kosha-loop | 0/0 | 0.00 | 0 |
| prompt-only | 0/0 | 0.00 | 0 |

Loop minus prompt-only safety: +0.00 (safety margin 0.25).

## Drift across sequential ingests

- Ingests: 50
- Corpus grew: 2 -> 51 concepts (+49)
- Maintenance accuracy before growth: 1.00
- Maintenance accuracy after growth: 1.00
- Edit-drift fidelity held: False
- Fidelity targeter: `generation:openai:openai/gpt-4.1-nano`

## Decision

**Verdict: NO-GO.**

Wins:
- none

Losses:
- knowledge-integrity safety: loop 0.00 vs prompt-only 0.00 (delta +0.00, margin 0.25); loop silent overwrites 0
- maintenance accuracy moved 1.00 -> 1.00 across 50 ingests as the corpus grew +49 (fidelity held: False)
- routing decision quality is a structural tie (loop +0.00 vs prompt-only; both call the same LLM) — reported as context, not gated
