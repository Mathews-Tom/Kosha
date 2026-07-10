# Paper Positioning Notes

This document contains canonical positioning sentences and a contribution boundary table for the Kosha paper draft, as defined in M1 (Claim hygiene and paper positioning).

## 1. VMG Operationalization Sentence

Kosha is the first operationalization and empirical evaluation of VMG-style governance primitives (arXiv:2604.16548). Where previous work conceptually proposed verifiable memory governance, Kosha implements append-only claims, content-addressed supersession, and branch-per-ingest review enforced in code.

## 2. Pre-LLM Human-Gated Curation Lineage Note

Kosha extends the mature pre-LLM human-gated curation lineage (e.g., Wikidata bot approval [OpenSym 2019], Saga [arXiv:2204.07309], and expert-routing [arXiv:2212.05189]) into the LLM-agent regime. By structurally requiring human review for LLM-authored knowledge base edits, Kosha addresses the governance gap in autonomous maintenance.

## 3. Contribution and Non-Claim Table

| Category | Claim / Scope | Kosha Position |
|---|---|---|
| **Contribution** | Governance Mechanism | Kosha enforces append-only claims, content-addressed supersession, and branch-per-ingest review in code. |
| **Contribution** | Evaluation Methodology | Kosha introduces pre-registered kill criteria, deterministic offline reproduction, and CI-enforced consistency between recorded verdicts and public claims. |
| **Contribution** | Empirical Finding | Under strict governance, the LLM-in-the-loop maintenance pipeline trails a well-instructed prompt-only baseline on decision quality, demonstrating that current LLMs require a safety scaffold. |
| **Non-Claim** | Decision-Quality Superiority | Kosha does **not** claim to beat a strong prompt-only baseline on maintenance decision quality. |
| **Non-Claim** | Retrieval Superiority | Kosha does **not** claim retrieval superiority over real-world RAG systems (deterministic numbers are self-consistency checks). |
| **Non-Claim** | Filesystem Sandboxing | Kosha exposes traversal tools, but does **not** currently sandbox a host agent with generic filesystem access. |

## 4. Fidelity Targeter Evidence (M4)

The §7.1 edit-drift fidelity probe (repeatedly superseding one claim and checking
that the body stays a byte-identical projection of the in-force claims) has two
targeters: the deterministic `LexicalClaimTargeter` (highest-Jaccard-overlap
match) and the real-model `GenerationClaimTargeter` (an LLM picks the claim a
new statement revises). Earlier acceptance and Gate-0 evidence — including the
M3 S2-v3 report (`.docs/s2-v3-report.md`) — recorded fidelity only under the
lexical targeter, which is exact by construction on its own synthetic loop and
cannot by itself demonstrate that a real model preserves the same guarantee.

A reviewed real-provider run (`.docs/real-model-fidelity-report.md`,
`openai:bge-m3` embeddings + `openai:openai/gpt-4.1-nano` generation via
OpenRouter, `bundles/paper-s2v3-corpus`, 50 sequential ingests,
`--fidelity-targeter generation`) closes that caveat: **edit-drift fidelity did
not hold** (`fidelity_targeter: generation:openai:openai/gpt-4.1-nano`,
`fidelity_ok: False`), unlike the lexical targeter's exact match on the same
probe shape. The paper must report this as an additional negative finding —
the governance mechanism's edit-drift guarantee, as currently implemented,
depends on the deterministic targeter and is not yet demonstrated to hold when
an LLM performs the claim-targeting judgment. Paper prose must not cite the
lexical-only fidelity result as evidence that a real model preserves fidelity.
