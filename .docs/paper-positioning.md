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
