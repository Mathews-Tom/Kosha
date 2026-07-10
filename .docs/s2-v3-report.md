# Kosha S2-v3 Provider-Matrix Acceptance Report (M3, Gate 0)

**Verdict: NO-GO** - the stricter rerun satisfies the pre-registered provider-matrix shape (one embedding model and two generation models from different vendors) but still does not clear the reframed kill criterion; ship Kosha as an OSS skill and halt M14+.

## Matrix setup

- Corpus: `bundles/paper-s2v3-corpus` (2 concepts, external)
- Embedding provider: `openai:bge-m3` via local OpenAI-compatible Ollama endpoint
- Generation providers:
  - `openai:openai/gpt-4.1-nano` via OpenRouter (OpenAI; $0.10/M input, $0.40/M output)
  - `openai:qwen/qwen3-235b-a22b-2507` via OpenRouter (Qwen; $0.09/M input, $0.10/M output)
- Held-out queries per cell: 1
- Maintenance cases per cell: 1
- Held-out contradiction cases per cell: 0
- Sequential ingests per cell: 50
- Report provenance:
  - `openai/gpt-4.1-nano`: `/tmp/kosha-s2v3-openai-gpt-4.1-nano.md`, sha256 `f367f4f62883231cf3a777388ce61841e7a396a6e674b4e0a8f90a4bfd289819`
  - `qwen/qwen3-235b-a22b-2507`: `/tmp/kosha-s2v3-qwen-235b.md`, sha256 `86db8cd4b7072b32339968474cba1bf4521a7904cba04975e12aa6fdda078ef6`

## Matrix verdict

Both generation-provider cells are NO-GO. `openai/gpt-4.1-nano` preserved maintenance accuracy across the 50-ingest drift path but had zero held-out contradiction cases, so it could not clear the safety-margin criterion. `qwen/qwen3-235b-a22b-2507` also had zero held-out contradiction cases and regressed maintenance accuracy from 1.00 to 0.00 across the 50-ingest drift path. Neither cell supports decision-quality or retrieval superiority claims.

## Cell: OpenAI GPT-4.1 Nano

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
| kosha-hybrid | 1.00 | 1.00 | 235 | 255 |
| tuned-rag | 1.00 | 1.00 | 235 | 254 |
| prompt-only | 1.00 | 1.00 | 247 | 690 |

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
- Corpus grew: 2 -> 52 concepts (+50)
- Maintenance accuracy before growth: 1.00
- Maintenance accuracy after growth: 1.00
- Edit-drift fidelity held: True
- Fidelity targeter: `lexical-jaccard-0.30`

## Decision

**Verdict: NO-GO.**

Wins:
- maintenance accuracy moved 1.00 -> 1.00 across 50 ingests as the corpus grew +50 (fidelity held: True)

Losses:
- knowledge-integrity safety: loop 0.00 vs prompt-only 0.00 (delta +0.00, margin 0.25); loop silent overwrites 0
- routing decision quality is a structural tie (loop +0.00 vs prompt-only; both call the same LLM) — reported as context, not gated


## Cell: Qwen Qwen3 235B A22B 2507

# Kosha Real-Model Acceptance Report (M13, Gate 0)

**Verdict: NO-GO** - the loop does not clear the reframed kill criterion; ship Kosha as an OSS skill and halt M14+.

## Setup

- Corpus: `bundles/paper-s2v3-corpus` (2 concepts, external)
- Embedding provider: `openai:bge-m3` (env: KOSHA_EMBED_BASE_URL=http://localhost:11434/v1, KOSHA_EMBED_MODEL=bge-m3, KOSHA_EMBED_API_KEY=unus..., KOSHA_EMBED_DIM=1024)
- Generation provider: `openai:qwen/qwen3-235b-a22b-2507` (env: KOSHA_GEN_BASE_URL=https://openrouter.ai/api/v1, KOSHA_GEN_MODEL=qwen/qwen3-235b-a22b-2507, KOSHA_GEN_API_KEY=sk-or-v...4817)
- Held-out queries: 1

## Kill criterion (fixed before the run)

GO only if (1) the loop preserves knowledge integrity under contradiction (conflict detected, prior claim retained, zero silent overwrites) on at least 25% more held-out contradictions than a safety-instructed prompt-only baseline and never silently overwrites, (2) maintenance accuracy does not drop by more than 5% across >=50 ingests that grow the corpus (>=90% add a concept), and (3) edit-drift fidelity holds. Otherwise NO-GO: ship Kosha as an OSS skill and halt M14+.

## Retrieval / answer quality (held-out queries)

| Strategy | Concept recall | Answer-keyword recall | Avg context tokens | Avg total tokens |
|---|---|---|---|---|
| kosha-hybrid | 1.00 | 1.00 | 235 | 272 |
| tuned-rag | 1.00 | 1.00 | 235 | 276 |
| prompt-only | 1.00 | 0.00 | 247 | 661 |

## Maintenance quality (held-out dedup / novel / contradiction)

| Decider | Accuracy | duplicate | novel | contradiction |
|---|---|---|---|---|
| kosha-loop | 0.00 (0/1) | 0.00 | 0.00 | 0.00 |
| prompt-only | 0.00 (0/1) | 0.00 | 0.00 | 0.00 |

Loop minus prompt-only maintenance accuracy: +0.00 (context only; routing is a structural tie and is not the reframed gate).

## Knowledge-integrity safety under contradiction (the reframed moat)

| Decider | Safe | Safety rate | Silent overwrites |
|---|---|---|---|
| kosha-loop | 0/0 | 0.00 | 0 |
| prompt-only | 0/0 | 0.00 | 0 |

Loop minus prompt-only safety: +0.00 (safety margin 0.25).

## Drift across sequential ingests

- Ingests: 50
- Corpus grew: 2 -> 48 concepts (+46)
- Maintenance accuracy before growth: 1.00
- Maintenance accuracy after growth: 0.00
- Edit-drift fidelity held: True
- Fidelity targeter: `lexical-jaccard-0.30`

## Decision

**Verdict: NO-GO.**

Wins:
- none

Losses:
- knowledge-integrity safety: loop 0.00 vs prompt-only 0.00 (delta +0.00, margin 0.25); loop silent overwrites 0
- maintenance accuracy moved 1.00 -> 0.00 across 50 ingests as the corpus grew +46 (fidelity held: True)
- routing decision quality is a structural tie (loop +0.00 vs prompt-only; both call the same LLM) — reported as context, not gated

