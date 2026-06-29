# Kosha Real-Model Acceptance Report (M13, Gate 0)

**Verdict: NO-GO** - the loop does not clear the kill criterion; ship Kosha as an OSS skill and halt M14+.

## Setup

- Corpus: `bundles/pydoc-stdlib` (680 concepts, external)
- Embedding provider: `openai:bge-m3`
- Generation provider: `openai:openai/gpt-4o-mini`
- Held-out queries: 26

## Kill criterion (fixed before the run)

GO only if (1) loop maintenance accuracy exceeds prompt-only by at least 10%, (2) maintenance accuracy does not drop by more than 5% across >=50 sequential ingests that actually grow the corpus (>=90% of ingests add a concept), and (3) edit-drift fidelity holds. Otherwise NO-GO: ship Kosha as an OSS skill and halt M14+.

## Retrieval / answer quality (held-out queries)

| Strategy | Concept recall | Answer-keyword recall | Avg context tokens | Avg total tokens |
|---|---|---|---|---|
| kosha-hybrid | 0.96 | 1.00 | 977 | 1082 |
| tuned-rag | 0.92 | 0.92 | 927 | 1025 |
| prompt-only | 1.00 | 0.96 | 1045 | 1527 |

## Maintenance quality (held-out dedup / novel / contradiction)

| Decider | Accuracy | duplicate | novel | contradiction |
|---|---|---|---|---|
| kosha-loop | 0.50 (12/24) | 0.42 | 1.00 | 0.17 |
| prompt-only | 0.79 (19/24) | 0.58 | 1.00 | 1.00 |

Loop minus prompt-only maintenance accuracy: -0.29 (notable margin 0.10).

## Drift across sequential ingests

- Ingests: 50
- Corpus grew: 80 -> 126 concepts (+46)
- Maintenance accuracy before growth: 0.67
- Maintenance accuracy after growth: 0.62
- Edit-drift fidelity held: True

## Decision

**Verdict: NO-GO.**

Wins:
- maintenance accuracy moved 0.67 -> 0.62 across 50 ingests as the corpus grew +46 (fidelity held: True)

Losses:
- maintenance accuracy delta vs prompt-only is -0.29
