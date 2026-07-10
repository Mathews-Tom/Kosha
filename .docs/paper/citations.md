# Citation Inventory

Every work cited anywhere in the Kosha paper package is listed here with a verifiable source identifier (an arXiv ID, a DOI, or a named venue/proceedings entry) and the one-line relation to Kosha that the paper draws. Citations are carried over from the literature review in `.docs/paper-feasibility-analysis.md` section 3, whose stated methodology verified every entry against a live search (arXiv, ACL Anthology, OpenReview, or publisher pages) before use; the same entries were independently spot-checked again while assembling this package. `tests/docs/test_paper_claims.py` checks that every row below carries a non-empty `Source` cell, so no citation can be added to this inventory without an identifier.

## RAG and graph retrieval

| Work | Source | Relation to Kosha |
|---|---|---|
| Retrieval-Augmented Generation (Lewis et al., NeurIPS 2020) | arXiv:2005.11401 | Founding RAG paradigm Kosha rejects at the retrieval layer (deterministic traversal, no vector search endpoint). |
| RAG survey (Gao et al., 2024) | arXiv:2312.10997 | Retrieval-time taxonomy; no maintenance/governance axis. |
| GraphRAG (Edge et al., Microsoft, 2024) | arXiv:2404.16130 | Machine-built, machine-maintained graph index over a corpus; no human review gate on graph construction or update. |
| HippoRAG (NeurIPS 2024) / HippoRAG 2 (ICML 2025) | arXiv:2405.14831, arXiv:2502.14802 | Continual-learning retrieval; no versioning, audit trail, or review workflow. |
| LightRAG (EMNLP Findings 2025) | arXiv:2410.05779 | "Incremental update" is automatic re-indexing, not a reviewed commit. |
| RAPTOR (Stanford, 2024) | arXiv:2401.18059 | Embedding-based hierarchical tree retrieval; no maintenance-governance concern. |
| Agentic RAG survey (2025) | arXiv:2501.09136 | Agentic control over querying the store, not over maintaining it. |

## Agent memory systems

| Work | Source | Relation to Kosha |
|---|---|---|
| MemGPT / Letta (2023) | arXiv:2310.08560 | Auto-paged memory tiers; no audit trail or human gate on writes. |
| Mem0 (2025) | arXiv:2504.19413 | LLM-routed ADD/UPDATE/DELETE/NOOP decisions applied autonomously and silently; no append-only history. |
| A-MEM (2025) | arXiv:2502.12110 | Self-organizing Zettelkasten-style memory links; no versioning or review. |
| Zep / Graphiti (2025) | arXiv:2501.13956 | Closest production system: bi-temporal knowledge graph with soft-delete invalidation gives real auditability, but maintenance is fully automatic (no human approval gate), retrieval is graph+vector, and evaluation targets retrieval accuracy/latency rather than governance safety. |
| MemOS (2025) | arXiv:2505.22101 | The MemCube abstraction carries provenance/version/lifecycle metadata; an architecture proposal with no git-native history, no review workflow, and no empirical governance evaluation. |
| Agent-memory omnibus survey (2026) | arXiv:2512.13564 | Broad taxonomy that lists "trustworthiness" as a frontier concern but does not define versioning, auditability, or human review as an evaluation axis. |
| VMG survey (2026) | arXiv:2604.16548 | Single closest prior work. Proposes Verifiable Memory Governance as a set of architectural primitives anchored in storage-time provenance, versioning, and policy-aware retention. Survey only: no implementation, no benchmark, no empirical evaluation, and no specified human-review workflow. Kosha is the first operationalization and empirical evaluation of VMG-style governance primitives. |

## Knowledge editing

| Work | Source | Relation to Kosha |
|---|---|---|
| ROME | arXiv:2202.05262 | Edits model weights directly; Kosha edits an external, human-legible document store and treats the model as a fixed consumer. |
| MEMIT (ICLR 2023) | arXiv:2210.07229 | Same weight-editing family as ROME; same distinction from Kosha applies. |
| Knowledge-editing survey (ACM TIST 2024) | arXiv:2310.16218 | Surveys the weight-editing subfield; does not cover external document-store governance. |
| Knowledge Conflicts survey (Xu et al., EMNLP 2024) | arXiv:2403.08319 | Diagnoses context-memory, inter-context, and intra-memory conflicts; proposes no prevention mechanism. Kosha's append-only claim layer plus review gate is a prevention mechanism outside this taxonomy. |

## Pre-LLM human-gated curation lineage

| Work | Source | Relation to Kosha |
|---|---|---|
| "Approving Automation" (Farda-Sarbas et al.) | OpenSym 2019 | Wikidata's formal human-approval process for bot-authored edits, running since before 2019; the earliest mature instance of human-gated KB curation Kosha extends into the LLM-agent regime. |
| Manzoor et al. | arXiv:2212.05189 | Routes knowledge-graph-expansion candidates to human experts before insertion. |
| Apple Saga | arXiv:2204.07309 | Gates served facts behind a curation step before they reach production. |

## KB construction and maintenance by LLMs

| Work | Source | Relation to Kosha |
|---|---|---|
| RepoAgent | arXiv:2402.16667 | Git-integrated documentation regeneration; docs are ancillary artifacts and review is not central to the design. |
| Git-Context-Controller | arXiv:2508.00031 | Closest technical analog to Kosha's git-native framing, but targets ephemeral agent context rather than a persistent, consulted knowledge base. |
| AgentGit | arXiv:2511.00628 | Git-like rollback for multi-agent state trajectories, not for a maintained knowledge store. |
| SkillX | arXiv:2604.04804 | Skill-knowledge-base construction; does not address maintenance governance. |

## Benchmarks

| Work | Source | Relation to Kosha |
|---|---|---|
| LoCoMo | arXiv:2402.17753 | Long-dialogue memory recall benchmark; measures retrieval, not maintenance safety. |
| LongMemEval (ICLR 2025) | arXiv:2410.10813 | Includes a "knowledge updates" ability but measures QA accuracy on a static constructed history, not whether an agent's own edit corrupted the store. |
| LeKUBE | arXiv:2407.14192 | Legal knowledge-update benchmark, framed around weight editing. |

Every benchmark above evaluates retrieval accuracy or edit efficacy. None asks whether an LLM agent's unsupervised maintenance edit corrupted the knowledge base, and whether a human reviewer would have caught it under a pre-registered protocol — the empty cell Kosha's evaluation targets, scoped against the pre-LLM Wikidata/Saga curation lineage above.
