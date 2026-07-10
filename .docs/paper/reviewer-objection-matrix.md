# Reviewer Objection Matrix

Every objection a peer reviewer could reasonably raise, sourced from `.docs/paper-feasibility-analysis.md` section 4's challenge round plus objections that emerged from the M3/M4 evidence produced after that analysis, each with a direct answer and an evidence cross-link. Per DEVELOPMENT_PLAN.md M9's acceptance row, every surviving challenge has an answer or an explicit limitation; none is hidden.

## Challenges from the original feasibility analysis (§4)

### 1. "The S2 negative result rests on one corpus and one powered model family — does it generalize?"

**Status at analysis time:** survived, hard blocker for peer review. **Now:** resolved. M3's S2-v3 experiment ran a second, non-Python-docs corpus (NASA Apollo Flight Journal transcripts) with two generation models from different vendors (`openai/gpt-4.1-nano`, `qwen/qwen3-235b-a22b-2507`) and returned NO-GO on both cells, the same qualitative outcome as the single-corpus S2 run. The negative result generalizes beyond one corpus and one vendor family. Evidence: `.docs/s2-v3-report.md`, `docs/gate0-status.md`, `.docs/paper/experiments-and-reproducibility.md` section C.

### 2. "VMG conceptually specifies your architecture — what's left to claim as novel?"

**Status at analysis time:** rebutted in the challenge round, but required an explicit positioning sentence not yet present in any repo doc. **Now:** resolved. `.docs/paper-positioning.md` section 1 states the VMG operationalization sentence explicitly; `.docs/paper/related-work.md` restates it in the VMG subsection and the summary delta table. A concept-only survey that calls for a system strengthens rather than preempts the first implementation-plus-evaluation paper, provided the positioning is explicit — it now is.

### 3. "Zero silent overwrites over N cases reads as an empirical benchmark win, not a structural guarantee — is it?"

**Status at analysis time:** conceded; `reconcile()` is structurally built to append or status-flip, so the invariant holds by construction and needed to be presented at that reduced altitude, once, rather than repeated as a benchmark statistic. **Now:** resolved. `.docs/paper-positioning.md` section 2, `.docs/paper/experiments-and-reproducibility.md` section A, and `.docs/paper/draft.md` section 3 (Mechanism) each state it once as a verified design invariant. `docs/gate0-status.md` and `README.md` carry the same canonical phrasing, machine-checked by `tests/docs/test_public_claims.py`'s `zero_silent_overwrite_invariant` disclosure rule.

### 4. "This reads as 'we built something worse than a prompt and dressed it up' — why is a negative result about your own system publishable?"

**Answer:** the Challenger's premise ruling from the feasibility analysis applies directly: a negative result about the authors' own system, with no external system evaluated, is publishable if it generalizes beyond one corpus/model family and is framed as a governance-safety-plus-methodology contribution rather than a system that beats anything. Both conditions now hold — the result generalizes (objection 1) and the paper's contribution statement (`.docs/paper/draft.md` section 1) explicitly separates governance value from decision-quality value, claiming only the former plus the evaluation methodology. The pre-registration discipline (`.docs/s2-v3-preregistration.md`, kill criteria fixed in code before every run) mitigates the residual "moved the goalposts" reading but does not eliminate a reviewer's right to independently judge the framing.

## Objections raised by evidence produced after the original analysis (M3/M4)

### 5. "Your edit-drift fidelity guarantee doesn't hold under a real generation-model targeter — doesn't this undermine the governance claim?"

**Answer:** no, because the two claims are distinct and the paper does not conflate them. The governance mechanism's *structural* guarantees (append-only claims, `assert_no_silent_overwrite`, branch-per-ingest review) are enforced in code independent of which targeter selects a claim to supersede, and hold regardless of this result. The *fidelity probe* specifically tests whether the deterministic lexical targeter can be swapped for a real LLM without introducing edit drift — M4 found it cannot yet, honestly reported as an additional negative finding (`fidelity_ok: False`, `.docs/real-model-fidelity-report.md`) rather than smoothed over or omitted. This narrows, not undermines, the claim: Kosha's shipped pipeline uses the lexical targeter by default specifically because the real-model alternative is not yet demonstrated safe.

### 6. "S2-v3's held-out sample (1 query, 0 contradiction cases per cell) is too small to support any conclusion."

**Answer:** conceded as a limitation, not hidden. `.docs/paper/experiments-and-reproducibility.md` section F states directly that the 0.00 safety rate on the Qwen cell reflects an empty sample, not a measured safety loss, and that this axis is disclosed as underpowered. The maintenance-accuracy-across-drift finding (1.00 -> 1.00 vs 1.00 -> 0.00) does not depend on the thin held-out set — it is measured across 50 sequential ingests per cell — and is the load-bearing generalization evidence; the safety axis is reported for completeness with its limitation attached, not used to strengthen the claim beyond what it supports.

### 7. "Zep/Graphiti claims real auditability — how do you know it lacks a human-approval gate?"

**Answer:** verified independently by two reviewers during the original literature review (Researcher B and an adversarial Challenger round), not asserted from a single read of Zep/Graphiti's documentation. `.docs/paper/citations.md` and `.docs/paper/related-work.md` state the finding with the citation (arXiv:2501.13956); the paper's claim is scoped to "no human-approval gate exists in the pipeline," not to Zep/Graphiti's auditability features generally, which are accurately credited as real.

## Objections a reviewer could raise about venue fit and remaining scope

### 8. "NORA is framed around knowledge graphs — Kosha is deliberately not a graph/vector retrieval system. Doesn't this paper not fit?"

**Answer:** disclosed directly in `.docs/paper/venue-verification.md` as a partial mismatch, not concealed. NORA's call for papers explicitly includes "Architectures for Persistent Agent Memory" and "Benchmarking Agent Memory Performance" as in-scope topics independent of graph representation, and the paper's related-work section states plainly that Kosha rejects the RAG/graph retrieval lineage at the retrieval layer by design. The contribution is governance architecture and evaluation methodology for agent-maintained memory, which is in scope even though the underlying representation is not a knowledge graph.

### 9. "Why publish a paper about a system whose product path is currently halted (M14+ NO-GO)?"

**Answer:** the paper's contribution is explicitly not "ship this as a product" — it is the governance mechanism (reusable independent of decision-quality verdict), the pre-registered evaluation methodology (reusable by any agent-autonomy evaluation), and the generalized negative finding itself (a result the field benefits from having on record, per the venue's explicit welcome of negative-results submissions). `.docs/paper/draft.md`'s conclusion states this separation directly.

### 10. "M6-M8 (ablations, review-burden telemetry, GraphRAG baseline) were not run — does this weaken the paper?"

**Answer:** no, by design. Those milestones are optional main-track upgrades (DEVELOPMENT_PLAN.md section D), not required for the NORA workshop-tier submission this M9 pass targets. Their absence is disclosed in `.docs/paper/experiments-and-reproducibility.md` and is not presented as a completed ablation study; the paper does not claim ablation-isolated primitive contributions it has not measured.

## Summary

Every challenge that survived the original adversarial review round has a resolution with an evidence cross-link. Every objection raised by evidence produced since then (M3, M4) has a direct answer or an explicit, undisguised limitation. No objection is answered by asserting a claim the checked-in evidence does not support.
