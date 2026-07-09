# Kosha Deterministic Self-Consistency Report

**Verdict: PASS** - the deterministic local-provider MVP mechanics hold on the reference corpus. This is not a real-model Gate-0 decision-quality result; current real-model Gate-0 status is **NO-GO** and M14+ remains halted. See `docs/gate0-status.md`.

## Setup

- Corpus: `bundles/northwind` (12 concepts)
- Embedding provider: `lexical-hash-256`
- Generation provider: `extractive-3`

Token figures are deterministic (fixed corpus, fixed queries, deterministic local providers); latency is wall-clock and environment-dependent, so the latency gate falls back to the deterministic round-trip comparison below the wall-clock noise floor.

## Criteria

| Criterion | Result | Target |
|---|---|---|
| C1-token-latency Hybrid token cost < RAG (at matched quality) and latency within RAG margin | PASS | hybrid total tokens < raw-docs baseline AND hybrid tokens-per-recall < RAG; hybrid latency within 2x RAG (round-trip comparison below 5ms wall-clock) |
| C2-duplicate-rate Duplicate-rate ~= 0 after repeated ingests | PASS | duplicate-rate <= 0.00 on a re-ingest of the corpus |
| C3-fidelity Fidelity preserved across >=20 sequential ingests | PASS | no edit-drift across >=20 ingests |
| C4-contradiction-safety Contradictions resolved-or-escalated | PASS | 100% of injected contradictions resolved-or-escalated |

### C1-token-latency — PASS

_Hybrid token cost < RAG (at matched quality) and latency within RAG margin_

tokens: hybrid 602 vs RAG 541 vs raw-docs 1131; concept recall: hybrid 1.00 vs RAG 0.62; tokens-per-recall: hybrid 602 vs RAG 865 (PASS); hybrid < raw-docs PASS. latency: hybrid 2 round-trips vs RAG 2, 0.34ms vs 0.49ms (0.69x, margin 2x; wall-clock below noise floor).

### C2-duplicate-rate — PASS

_Duplicate-rate ~= 0 after repeated ingests_

re-ingesting 12 existing concepts: 0 CREATE / 12 UPDATE; duplicate-rate 0.000.

### C3-fidelity — PASS

_Fidelity preserved across >=20 sequential ingests_

20 sequential ingests: body==claim projection True; every in-force claim grounded True; unrelated claim byte-identical True; OKF-conformant each step True; latest statement reflected, telephone-game absent True.

### C4-contradiction-safety — PASS

_Contradictions resolved-or-escalated_

12 injected contradictions: 12 detected; 11 resolved (temporal/authority) + 1 escalated = 12 handled; 0 silent overwrites.

## Decision

All deterministic self-consistency criteria: **PASS**. The reference-corpus mechanics meet their measured contract, but this report does not authorize decision-quality superiority or M14+ product expansion.
