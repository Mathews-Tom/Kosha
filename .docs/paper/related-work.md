# Related Work

Every citation below is listed with a verifiable identifier in `.docs/paper/citations.md`. This section positions Kosha against the closest prior work in five areas: RAG and graph retrieval, agent memory systems, knowledge editing, the pre-LLM human-gated curation lineage, and benchmarks for agent-maintained knowledge.

## RAG and graph retrieval

Retrieval-Augmented Generation (arXiv:2005.11401) and its survey literature (arXiv:2312.10997) treat the knowledge store as a retrieval index to be searched, not a document to be governed. GraphRAG (arXiv:2404.16130) builds and re-summarizes a knowledge graph from a corpus automatically, with no human review gate on graph construction or update; HippoRAG and HippoRAG 2 (arXiv:2405.14831, arXiv:2502.14802) add continual-learning retrieval without versioning or an audit trail; LightRAG (arXiv:2410.05779) reindexes incrementally, which is automatic re-indexing rather than a reviewed commit; RAPTOR (arXiv:2401.18059) builds an embedding-based retrieval tree; and the 2025 agentic-RAG survey (arXiv:2501.09136) covers agentic control over *querying* a store, not over *maintaining* one. None of this lineage treats governed maintenance as a first-class concern — the retrieval layer optimizes representation and search, and none of it asks whether an autonomous edit to the underlying store was safe.

Kosha deliberately rejects this lineage at the retrieval layer: production consumption is deterministic traversal over a Markdown knowledge bundle, not a vector-search endpoint, and the deterministic hybrid-vs-RAG token numbers in this package are internal self-consistency checks on toy providers, not a claim of retrieval superiority over any of the systems above.

## Agent memory systems

MemGPT/Letta (arXiv:2310.08560) pages memory automatically with no audit trail or human gate; Mem0 (arXiv:2504.19413) routes ADD/UPDATE/DELETE/NOOP decisions autonomously and silently, with no append-only history; A-MEM (arXiv:2502.12110) organizes memory as a self-organizing Zettelkasten with no versioning or review step.

Two systems are close enough to require an explicit delta.

**Zep/Graphiti** (arXiv:2501.13956) is the closest production system: a bi-temporal knowledge graph with soft-delete invalidation gives it real auditability — outdated facts are invalidated rather than deleted, and every edge carries validity intervals. But its maintenance loop is fully automatic; no human-approval gate exists in the pipeline. Its evaluation targets retrieval accuracy and latency (Deep Memory Retrieval, LongMemEval), not governance safety of the maintenance process itself. Kosha adds a hard structural review gate (branch-per-ingest, human-reviewed merge) and a governance-safety evaluation Zep/Graphiti's benchmark suite does not measure.

**MemOS** (arXiv:2505.22101) proposes the MemCube abstraction, which carries write-time provenance and versioning metadata as part of a unified memory-management architecture. It is an architecture proposal: no git-native history, no review workflow, and no empirical governance evaluation accompanies it. Kosha adds the git-native append-only history, the review workflow, and the empirical evaluation MemOS's design leaves open.

A broader agent-memory taxonomy (arXiv:2512.13564) surveys 47 systems and names "trustworthiness" as a frontier concern, but does not define versioning, auditability, or human review as an evaluation axis — the gap this paper's related work targets is not addressed by that survey either.

**Verifiable Memory Governance (VMG)** (arXiv:2604.16548, 2026) is the single closest prior work. The survey argues that memory security cannot be retrofitted at retrieval or execution time and must be anchored in storage-time provenance, versioning, and policy-aware retention, and proposes Verifiable Memory Governance as a small set of architectural primitives toward that end. It is survey-only: no implementation, no benchmark, no empirical evaluation, and no specified human-review workflow accompanies the proposal. **Kosha is the first operationalization and empirical evaluation of VMG-style governance primitives** — append-only claims, content-addressed supersession, and branch-per-ingest review enforced in code, evaluated against a prompt-only baseline under a pre-registered protocol. A delta table against VMG is not sufficient positioning on its own: this sentence must appear explicitly, or a reviewer familiar with the survey could read VMG as prior claim to the idea Kosha implements and evaluates.

## Knowledge editing

ROME (arXiv:2202.05262) and MEMIT (arXiv:2210.07229, ICLR 2023) edit model weights directly; the knowledge-editing survey (arXiv:2310.16218, ACM TIST 2024) covers the same weight-editing subfield. Kosha edits an external, human-legible document store and treats the underlying model as a fixed consumer of that store — a different edit surface entirely, not a competing technique on the same one. The Knowledge Conflicts survey (arXiv:2403.08319, EMNLP 2024) diagnoses context-memory, inter-context, and intra-memory conflicts but proposes no prevention mechanism; Kosha's append-only claim layer plus review gate is a prevention mechanism that sits outside that survey's taxonomy.

## Pre-LLM human-gated curation lineage

Human-gated knowledge-base curation is a mature, decade-old area that predates the current wave of LLM-agent memory systems, and any claim that "no benchmark evaluates governance-safety of autonomous maintenance" is incomplete without citing it. Wikidata has run a formal human-approval process for bot-authored edits since before 2019 ("Approving Automation," Farda-Sarbas et al., OpenSym 2019); Manzoor et al. (arXiv:2212.05189) route knowledge-graph-expansion candidates to human experts before insertion; Apple's Saga (arXiv:2204.07309) gates served facts behind a curation step before they reach production. **Kosha extends this pre-LLM, human-gated curation lineage into the LLM-agent regime**: the reviewer is no longer validating a bot's structured edit proposal but an LLM-authored Markdown claim, and the same append-only-plus-review discipline that Wikidata and Saga apply to bot edits is enforced in code for agent-authored edits here.

Adjacent to this lineage, the Karpathy "LLM Wiki" gist (April 2026) is the exact practitioner pattern Kosha formalizes — a raw-document store maintained by an agent-generated Markdown wiki with ingest/query/lint commands — with zero academic formalization: no versioning, review gate, audit log, or evaluation. The Open Knowledge-catalog Format (OKF) spec that Kosha's bundle format targets versions the *format* itself but defines no governance structure, review process, or maintenance procedure; independent implementations of the spec are tooling only, and no academic publication on OKF or LLM-wiki maintenance governance exists. RepoAgent (arXiv:2402.16667) regenerates documentation from a git-integrated pipeline but treats docs as ancillary artifacts with review not central to the design; Git-Context-Controller (arXiv:2508.00031) is the closest technical analog to Kosha's git-native framing but targets ephemeral agent *context*, not a persistent consulted knowledge base; AgentGit (arXiv:2511.00628) provides git-like rollback for multi-agent *state trajectories*, not a maintained KB; SkillX (arXiv:2604.04804) constructs a skill knowledge base but does not address its ongoing maintenance governance.

## Benchmarks

LoCoMo (arXiv:2402.17753) measures long-dialogue memory recall. LongMemEval (arXiv:2410.10813, ICLR 2025) includes a "knowledge updates" ability among its evaluated skills but measures QA accuracy on a static, pre-constructed history — it does not ask whether the agent's own maintenance edit corrupted the store. LeKUBE (arXiv:2407.14192) evaluates legal knowledge updates framed as weight editing, and zsRE/CounterFact-style benchmarks measure single-fact weight-edit efficacy. Every benchmark in this space evaluates retrieval accuracy or edit efficacy; none evaluates whether an LLM agent's unsupervised edit corrupted a knowledge base under a pre-registered protocol, and whether a human reviewer would have caught it. Scoped against the pre-LLM Wikidata/Saga curation lineage above — rather than presented as an unqualified gap in a mature field — this is the empty cell Kosha's evaluation targets.

## Summary delta table

| Prior work | Has | Kosha adds |
|---|---|---|
| VMG survey (arXiv:2604.16548) | The conceptual architecture: storage-time provenance, versioning, auditable governance | A working implementation, a pre-registered empirical evaluation, and an honest negative result |
| Zep/Graphiti (arXiv:2501.13956) | Bi-temporal versioning and soft-delete auditability | A hard structural human-review gate, deterministic traversal, and a governance-safety evaluation |
| MemOS (arXiv:2505.22101) | Write-time provenance metadata via the MemCube abstraction | Git-native append-only history, a review workflow, and an empirical evaluation |
| Wikidata bot governance / Saga / Manzoor et al. | Mature human-gated curation of bot-authored KB edits | Extension to LLM-agent authors, a Markdown-bundle substrate, and a pre-registered autonomy evaluation with negative findings |
| Karpathy LLM-wiki gist / OKF spec | The practitioner pattern and the bundle format | Governance theory, enforcement in code, and empirical evaluation |
| LongMemEval | A "knowledge updates" QA dimension | Maintenance-safety evaluation of the editing agent itself |
