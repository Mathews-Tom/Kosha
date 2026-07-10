# Kosha: Git-Native Governance for Agent-Maintained Knowledge Bundles — Mechanisms, Pre-Registered Evaluation, and Negative Results on Real-Model Autonomy

Working title; component sections live in `.docs/paper/related-work.md`, `.docs/paper/experiments-and-reproducibility.md`, `.docs/paper/evidence-ledger.md`, `.docs/paper/citations.md`, and `.docs/paper-positioning.md`. This document assembles them into a coherent draft with an abstract, introduction, mechanism description, results framing, and conclusion; it does not restate their full content, only summarizes and links it.

## Abstract

We present Kosha, a git-native governance layer for agent-maintained Markdown knowledge bundles. Kosha enforces append-only claims, content-addressed supersession, and branch-per-ingest human review in code; zero silent overwrite is verified as a design invariant rather than measured as an empirical result. We test whether an LLM-in-the-loop maintenance pipeline, built inside this governance scaffold, beats a well-instructed prompt-only baseline on maintenance decision quality. Across four pre-registered real-model runs — a single-corpus Gate-0 evaluation, a scaled 108-case single-corpus replication, a second-corpus cross-vendor replication, and a real-model fidelity probe — every real-model Gate-0 run records a NO-GO verdict: the loop trails the prompt-only baseline on detection and safety by 0.28-0.33 in the powered matrix, and edit-drift fidelity does not hold once claim-targeting is delegated to a real generation model rather than a deterministic lexical match. We report this as a generalized negative result: the governance mechanism and evaluation methodology are the contribution, not a claim that current LLMs earn maintenance autonomy inside this or any safety scaffold. Kosha ships as an open-source governance skill; production maintenance-loop expansion (M14+) stays halted pending a future pre-registered run that records a GO verdict.

## 1. Introduction

Agent-maintained knowledge stores are proliferating faster than the governance discipline that decade-old, pre-LLM curation systems (Wikidata bot approval, Apple's Saga) already established for bot-authored edits (see `.docs/paper/related-work.md` section "Pre-LLM human-gated curation lineage"). Recent memory-system proposals add auditability primitives — Zep/Graphiti's bi-temporal knowledge graph, MemOS's provenance-carrying MemCube, the VMG survey's conceptual governance framework — but none combines a git-native, human-reviewed edit history with an empirical evaluation of whether an LLM earns the autonomy such a scaffold would grant it.

**Research questions:**

1. Can agent-maintained knowledge bundles be governed such that silent overwrite is structurally impossible while remaining fully replayable? Answer: yes — a mechanism contribution (section 3; zero silent overwrites verified across every real-model run in this package).
2. Do current LLMs, embedded in such a governance loop, match or beat prompt-only baselines on maintenance decision quality? Answer: no — the loop does not currently beat prompt-only baselines under this protocol, a negative result now generalized across two corpora and multiple vendor models (section 5).
3. What evaluation discipline makes negative findings on agent autonomy credible rather than self-serving? Answer: pre-registration, determinism, and CI-enforced consistency between recorded verdicts and public claims — a methodology contribution (section 4).

**Contribution statement:**

1. A governance mechanism for agent-maintained Markdown knowledge bundles in which append-only claims, content-addressed supersession, branch-per-ingest review, and OKF conformance validation are enforced in code — the first operationalization and empirical evaluation of VMG-style governance primitives (arXiv:2604.16548), extending the pre-LLM human-gated curation lineage (Wikidata bot approval, Saga) into the LLM-agent regime.
2. A pre-registered evaluation methodology: kill criteria fixed before measurement, deterministic offline reproduction, and a CI check (`tests/bench/test_realworld_status.py`) that fails the build if the public verdict document drifts from the recorded verdict.
3. A generalized honest negative result: under this protocol, across a single-corpus powered matrix and a second-corpus cross-vendor replication, the real-model Gate-0 verdict is NO-GO — the LLM-in-the-loop maintenance pipeline trails a well-instructed prompt-only baseline on contradiction detection and safety, and its edit-drift fidelity guarantee does not yet hold under a real generation-model claim targeter — evidence that governance value and decision-quality value are separable.

What this paper does not claim (full non-claim table in `.docs/paper-positioning.md` section 3): the paper does not claim decision-quality superiority over a well-instructed prompt; it does not claim retrieval superiority over real-world RAG systems (the deterministic hybrid-vs-RAG numbers in this package are internal self-consistency checks on toy providers); and it does not claim filesystem sandboxing (the shipped MCP server exposes traversal tools and is not a sandboxing boundary).

## 2. Related Work

Summarized in full in `.docs/paper/related-work.md`. In brief: the RAG and graph-retrieval lineage (RAG, GraphRAG, HippoRAG, LightRAG, RAPTOR) optimizes representation and search, not governed maintenance. Agent memory systems (MemGPT, Mem0, A-MEM, Zep/Graphiti, MemOS) add auditability or temporal structure but automate maintenance without a human-review gate, or propose governance architecture without an implementation and evaluation. The VMG survey (arXiv:2604.16548) is the single closest prior work — Kosha is its first operationalization and empirical evaluation. Knowledge-editing work (ROME, MEMIT) edits model weights, a different surface than Kosha's external document store. The pre-LLM human-gated curation lineage (Wikidata bot approval, Manzoor et al., Saga) is the direct ancestor Kosha extends into the LLM-agent regime. No existing benchmark (LoCoMo, LongMemEval, LeKUBE) evaluates whether an agent's own unsupervised maintenance edit corrupted the store under a pre-registered protocol — the gap this paper's evaluation targets.

## 3. Mechanism

Kosha's governance mechanism has five enforced properties, each backed by code and tests (see `.docs/paper-feasibility-analysis.md` section 2.1 for the full enforcement audit):

- **Append-only claim layer, content-addressed supersession** (`src/kosha/merge/claims.py`, `lineage.py`, `reconstruct.py`) — a claim is `current`, `superseded`, or `contradicted`; it is never mutated in place.
- **`assert_no_silent_overwrite` invariant** (`src/kosha/contradiction/escalate.py`), invoked at every merge boundary — a verified design invariant of `reconcile()`, stated once at that altitude rather than repeated as an empirical benchmark statistic.
- **Contradiction routing** (temporal -> authority -> escalate, `src/kosha/contradiction/`) — deterministic diff and policy; an LLM is consulted only for the "materially conflicts" judgment.
- **Git-branch-per-ingest review flow** (`src/kosha/git_store.py`) — every ingest is a reviewable branch merge, not a direct write.
- **OKF conformance validation** (`src/kosha/validate.py`), CI-gated on every commit.

## 4. Methodology

Every real-model claim in this package follows the same discipline: pre-registered criteria fixed in code before measurement, a deterministic offline reproduction path that runs the same code with local providers, and a doc-drift CI check (`tests/bench/test_realworld_status.py`) that fails the build if `docs/gate0-status.md`'s public verdict text is not machine-generated from the recorded report. This is what makes the negative results in section 5 auditable rather than asserted: `docs/gate0-status.md`, `.docs/s2-v3-report.md`, and `.docs/real-model-fidelity-report.md` are generated artifacts, not hand-authored prose, and `.docs/paper/evidence-ledger.md` links every numeric claim in this package to one of them.

## 5. Experiments and Results

Full setup, provider identities, and per-run numbers are in `.docs/paper/experiments-and-reproducibility.md`. Summary:

- **Deterministic self-consistency** (section A): all mechanics hold on the reference corpus under local providers — a self-consistency check on toy providers, not a real-model or real-RAG result.
- **Single-corpus Gate-0** (section B, M13/S2): three pre-registered runs on `pydoc-stdlib`, all real-model NO-GO — the loop trails a well-instructed prompt-only baseline by 0.28-0.33 on detection and safety across all 8 provider cells in the powered matrix, corroborated by a cross-vendor smoke.
- **S2-v3 second-corpus, cross-vendor replication** (section C, M3): a new, non-Python-docs corpus (NASA Apollo Flight Journal transcripts) with two generation models from different vendors — NO-GO on both cells. The negative result generalizes beyond the single corpus and single vendor family that the pre-submission analysis flagged as a hard blocker.
- **Real-model fidelity** (section D, M4): swapping the deterministic lexical claim targeter for a real generation-model targeter — edit-drift fidelity does not hold (`fidelity_ok: False`), closing the fidelity caveat with an additional honest negative finding rather than continuing to present the lexical-only result as real-model evidence.

**Decision rule applied:** the pre-registered plan for this paper stated that if S2-v3 also returned NO-GO, the paper would remain a generalized negative result; if it returned GO, the framing would pivot to a conditional-autonomy story. S2-v3 returned NO-GO on both cells, so this paper is a generalized negative result, not a conditional-autonomy paper — the stronger and more publication-relevant outcome was decided by the data, not chosen after the fact.

## 6. Limitations

Full list in `.docs/paper/experiments-and-reproducibility.md` section F. Headline limitations: the S2-v3 held-out sample is thin (1 query, 0 contradiction cases per cell), so its safety axis reflects an empty sample rather than a measured loss; the real-model fidelity result is a single generation-model run, not yet a cross-vendor matrix; and paid-model outputs are not exactly reproducible, only qualitatively so.

## 7. Conclusion

Kosha demonstrates that governance value and decision-quality value are separable: the zero-silent-overwrite guarantee and replayable claim lineage are real and verified in code, independent of whether the LLM inside the loop makes good maintenance decisions. Across every pre-registered real-model run in this package — spanning two corpora, multiple generation-model vendors, and both the decision-quality and fidelity axes — the real-model Gate-0 verdict stays NO-GO: current LLMs do not yet earn the autonomy this governance scaffold would grant them. Kosha ships as an open-source governance skill; the mechanism and the evaluation methodology are offered as reusable contributions independent of that verdict, and production maintenance-loop expansion (M14+) stays halted until a future pre-registered run records a GO.
