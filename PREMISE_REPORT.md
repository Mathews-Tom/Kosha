# Kosha Premise-Validation Report

**Verdict: GO** - no kill signal fired; Sections C-F are authorized.

## Setup

- Corpus: `bundles/northwind` (12 concepts, max path depth 3)
- Queries: 8
- Embedding provider: `lexical-hash-256`
- Generation provider: `extractive-3`
- Seed dedup pairs: 24 (10 ambiguous-band)
- Seed granularity labels: 8 (lint accuracy 1.00)

Token and quality figures are deterministic (fixed corpus, fixed queries, deterministic local providers); latency is wall-clock and environment-dependent. `count_tokens` is a model-neutral estimate used for relative comparison.

## Strategy comparison

| Strategy | Avg context tokens | Avg total tokens | Retrieval+gen round-trips | Avg latency (ms) | Concept recall | Answer-keyword recall |
|---|---|---|---|---|---|---|
| hybrid | 470 | 602 | 2 | 0.29 | 1.00 | 0.88 |
| rag | 400 | 541 | 2 | 0.44 | 0.62 | 0.62 |
| long_context | 972 | 1131 | 1 | 0.29 | 1.00 | 0.75 |

Strategy roles: **hybrid** and the embedding index are production-grade and reused downstream; **rag** and **long_context** are benchmark-only baselines.

## Kill signals

### KS1-long-context — PASS — premise holds

_Does long-context-with-raw-docs match quality at acceptable cost?_

long-context concept recall 1.00 vs hybrid 1.00; long-context costs 1.88x hybrid total tokens (1131 vs 602); acceptable-cost margin 1.5x. Token gap widens with corpus size (traversal cost is bounded by depth, not corpus size).

### KS2-traversal-latency — PASS — premise holds

_Is hybrid within a usable latency margin of one RAG hop?_

hybrid 2 retrieval+gen round-trips vs RAG 2; hybrid latency 0.29ms vs RAG 0.44ms (0.66x, margin 2.0x). Round-trip parity is deterministic; wall-clock is a local-compute proxy and should be re-confirmed against a network provider.

### KS3-dedup-by-prompt — PASS — premise holds

_Does a single similarity threshold close the dedup gap?_

best threshold-only accuracy 0.75 at cosine>=0.211 over 24 pairs; 6/10 ambiguous-band pairs still misclassified; bar 0.95. Residual ambiguous band is where the loop's LLM adjudication earns its place.

## Decision

All three kill signals: **GO**. Proceed to M5+ (producer loop), re-anchoring claims on measured token savings, retrieval quality, and coherence/governance.
