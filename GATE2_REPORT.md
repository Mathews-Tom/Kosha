# Kosha Gate-0 v2 Re-Test

**Verdict: NO-GO** - NO-GO: keep Kosha a shipped OSS skill; M14+ stays halted.

**M14+ authorized: False**

## Pre-registered criterion (fixed before measurement)

GO only if a quality axis (detection_recall, safety_rate) clears a median margin of >=15% with the non-determinism noise band excluded (loop worst run > prompt best run) on EVERY provider cell, the loop never silently overwrites, and the re-test is powered: >=100 held-out contradictions spanning 6 regimes (numeric, negation, unit, partial, temporal, adversarial), >=3 runs per cell, across >=2 embeddings x >=2 generation models. A structural guarantee (zero silent overwrites) is necessary but is not a quality win and cannot authorize M14+ on its own. Otherwise NO-GO: keep Kosha an OSS skill; M14+ stays halted.

## Setup

- Corpus: `bundles/pydoc-stdlib` (680 concepts, external)
- Embeddings: bge-m3, nomic
- Generation models: gpt-4o-mini, gpt-4.1-mini
- Runs per cell: 3
- Held-out contradictions per cell: 108
- Regimes: numeric, negation, unit, partial, temporal, adversarial

## Power (pre-registered admissibility)

- Provider matrix (>=2x2): yes
- Sample size (>=100): yes
- Runs (>=3): yes
- Regime coverage (6): yes
- Loop never silently overwrites: yes

## Per-axis distributions (median [min, max], loop vs prompt-only)

| Embedding | Generation | Axis | Loop | Prompt-only | Δmedian | Noise excluded | Cleared |
|---|---|---|---|---|---|---|---|
| bge-m3 | gpt-4o-mini | detection_recall | 0.67 [0.66, 0.67] | 1.00 [1.00, 1.00] | -0.33 | no | no |
| bge-m3 | gpt-4o-mini | safety_rate | 0.67 [0.66, 0.67] | 1.00 [0.99, 1.00] | -0.33 | no | no |
| bge-m3 | gpt-4.1-mini | detection_recall | 0.67 [0.67, 0.67] | 1.00 [0.98, 1.00] | -0.33 | no | no |
| bge-m3 | gpt-4.1-mini | safety_rate | 0.67 [0.67, 0.67] | 0.94 [0.94, 0.97] | -0.28 | no | no |
| nomic | gpt-4o-mini | detection_recall | 0.67 [0.66, 0.67] | 1.00 [1.00, 1.00] | -0.33 | no | no |
| nomic | gpt-4o-mini | safety_rate | 0.67 [0.66, 0.67] | 1.00 [0.99, 1.00] | -0.33 | no | no |
| nomic | gpt-4.1-mini | detection_recall | 0.67 [0.67, 0.67] | 1.00 [0.98, 1.00] | -0.33 | no | no |
| nomic | gpt-4.1-mini | safety_rate | 0.67 [0.67, 0.67] | 0.94 [0.94, 0.97] | -0.28 | no | no |

## Auditability (necessary condition; a guarantee, not a quality win)

- No-silent-overwrite guarantee verified: yes (108 cases, 0 violations)
- Claim supersede lineage replayable: yes
- Branch-per-ingest provenance replayable: yes
- Prompt-only equivalent: none - a prompt offers no machine-verifiable guarantee and no per-change branch/claim trail to replay, at any rate.

## Decision

**Verdict: NO-GO.** Kosha ships as an OSS skill; M14+ stays halted.

Why:
- no quality axis cleared the margin with the noise band excluded on every cell - the loop did not beat a good prompt at scale

## Interpretation

The loop's code-owned detectors (numeric / negation / Jaccard) deterministically catch the numeric-cued regimes (numeric, negation, and the release-numbered temporal cases) at ~0.67 recall. On the subtle regimes (unit, partial, adversarial) the gate defers to the loop's contradiction judge, whose strict "materially contradicts" framing the real models answer *compatible* — so those conflicts are missed. A safety-instructed prompt ("preserve the prior statement and flag the conflict") flags ~all of them. The loop therefore loses detection and safety by 0.28–0.33 on every cell, with the N=3 intervals far outside the non-determinism noise band. This is the M13 finding at scale: on decision quality the loop does not beat a good prompt — it loses.

The loop's auditability guarantee holds end-to-end (zero silent overwrites over 108 contradictions; replayable supersede lineage + branch-per-ingest). That is a real, binary capability a prompt cannot match — but it is a governance guarantee, not a quality win, and the pre-registered criterion (fixed before this run) does not let it authorize M14+ on its own.

## Corroboration (cross-vendor)

A pre-run smoke over a 12-case regime-spanning subset with a cross-vendor generation model (`meta-llama/llama-3.3-70b-instruct`) showed the same pattern — loop detection 0.50 vs prompt-only 1.00, loop safety 0.50 vs prompt 0.92–1.00 — so the loss is not specific to the OpenAI generation models used in the powered matrix.

## Decision: M14+ remains HALTED

Per the pre-registered kill criterion, the verdict is **NO-GO**. Kosha ships as an OSS skill; the maintenance-loop product (M14+) is **not authorized** and stays halted. A GO would have required a quality axis to clear a >=15% median margin with the noise band excluded on every cell — the loop cleared none (it is negative on all). The auditability guarantee remains Kosha's honest differentiator for governance-sensitive buyers, but it is sold as a guarantee, not as "better than a prompt."
