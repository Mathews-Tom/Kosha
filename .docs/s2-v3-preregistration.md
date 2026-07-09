# S2-v3 Cross-Vendor Replication: Pre-Registration

This document pre-registers the evaluation criteria, provider matrix shape, case counts, and semantics for the S2-v3 cross-vendor replication experiment (DEVELOPMENT_PLAN.md §4 M3).

## Provider Matrix Shape
The experiment requires a minimum of:
- One embedding model.
- At least two generation models from different vendors (e.g., OpenAI `gpt-4o-mini` and Meta `llama-3.3-70b`).
- Local-smoke providers (`LexicalEmbeddingProvider`, `ExtractiveGenerationProvider`) are strictly for offline verification and do not constitute a valid Gate-0 verdict.

## Case Counts
- **Corpus**: `bundles/paper-s2v3-corpus` (historical spaceflight operations).
- **Queries**: Minimum 1 held-out query case.
- **Maintenance**: Minimum 1 held-out maintenance/contradiction case.

## Pre-Registered Criteria
The LLM-in-the-loop maintenance pipeline will be evaluated against a prompt-only baseline.
1. **Detection Recall**: The pipeline must achieve parity or superior recall on detecting injected contradictions.
2. **Safety Rate**: The pipeline must avoid silent overwrites entirely (enforced by the `reconcile` mechanism).

## GO/NO-GO Semantics
- **GO**: The pipeline demonstrates a safety or decision-quality advantage over the prompt-only baseline that justifies the governance overhead.
- **NO-GO**: The pipeline trails the prompt-only baseline on decision quality. If local-smoke providers are used for a full-scale run, the result is automatically invalid as a real-world verdict.
