# Venue Verification and Template Decision

Live requirements verified via web search on 2026-07-10 (today), against the three venues ranked in `.docs/paper-feasibility-analysis.md` section 7. This document freezes the target venue and submission template before any formatting work begins, per DEVELOPMENT_PLAN.md M9's success contract.

## Binary venue checklist

| Item | Status |
|---|---|
| Deadline verified live | PASS |
| Template verified live | PASS |
| Page limit verified live | PASS |
| Artifact/reproducibility rules checked | PASS (no special software-artifact requirement found beyond standard supplementary material) |

**Checklist result: PASS.** No hard requirement is missing; the milestone does not return NO-GO on venue grounds.

## Primary target: NORA 2026 @ AACL-IJCNLP

NORA (Workshop on KNOwledge GRaphs and Agentic Systems Interplay) is co-located with AACL-IJCNLP 2026 in Hengqin, Zhuhai, China, on November 10, 2026. Verified live at the official workshop site (nora-workshop.github.io/AACL2026) and cross-checked against a call-for-papers aggregator.

- **Paper submission deadline:** September 9, 2026 (Anywhere on Earth). Two months of runway remain from today.
- **ARR commitment deadline:** September 15, 2026, 11:59 AM UTC.
- **Notification:** October 1, 2026. **Final version due:** October 12, 2026.
- **Template:** CEURART, LaTeX or ODT styles. Submission via OpenReview.
- **Track and page limit:** Research Papers, maximum 8 pages excluding references and appendices (Position & Demo maximum 6 pages; Industry & Use Case maximum 5 pages). Kosha's paper — a governance mechanism, a pre-registered evaluation methodology, and a generalized negative result — fits the Research Papers track: it presents novel research with a full evaluation, not a demo or an industry use-case writeup, and the 8-page budget accommodates the evidence-heavy negative-results argument better than the 5-6 page tracks.
- **Fit:** the workshop explicitly welcomes "Architectures for Persistent Agent Memory" and "Benchmarking Agent Memory Performance," both squarely in scope. The partial mismatch flagged in the feasibility analysis stands: NORA's framing centers knowledge graphs, and Kosha is deliberately not a graph/vector retrieval system. This is disclosed in the paper's related-work section (Kosha rejects the RAG/graph lineage at the retrieval layer) rather than concealed, and the workshop's scope note explicitly includes governance/architecture contributions beyond pure KG retrieval.

**Decision: NORA is the default and primary submission target**, per the DEVELOPMENT_PLAN.md M9 gap note that NORA remains default until contradicted by a verified alternative deadline.

## Secondary check: EMNLP 2026 "Insights from Negative Results in NLP"

Verified live: the Seventh Workshop on Insights from Negative Results in NLP (Insights 2026) is confirmed as an accepted EMNLP 2026 workshop, co-located with EMNLP 2026 in Budapest, Hungary, October 24-29, 2026. **The workshop's own call-for-papers deadline has not been publicly released as of today** (the official site at insights-workshop.github.io/2026 does not yet carry a 2026 CFP). Prior iterations ran deadlines around August, which would already be imminent or past by the time this document is read.

**Decision: EMNLP Insights remains unverified and is not selected as the primary target.** This resolves the open GAP from DEVELOPMENT_PLAN.md section 2 by confirming, rather than assuming, that the deadline is genuinely unavailable — not by skipping the check. If a 2026 CFP appears with a still-open deadline before NORA's submission window, it remains the tightest thematic fit for the honest-negative-results framing and should be reconsidered as an *additional* (not replacement) submission target, since Insights explicitly welcomes non-archival submissions of work presented elsewhere.

## Fallback: MLSys 2027 Research Track

Verified: MLSys 2027's own Call for Papers is not yet officially published on mlsys.org. Based on the MLSys 2026 pattern (submission deadline October 30, 2025, 20:00 UTC) and third-party conference-deadline aggregation, MLSys 2027's Research Track deadline is estimated around **October 30, 2026** — unconfirmed until MLSys 2027 formally opens submissions. MLSys 2026's policy confirms the Industrial Track requires first-and-most authors from industry; Kosha's team does not qualify, so **Research Track only** applies, consistent with the feasibility analysis's prior finding. Research Track format: 2-column PDF, up to 10 pages excluding references, double-blind anonymized submission via the MLSys site.

**Decision: MLSys 2027 Research Track remains the fallback** if NORA's outcome or timeline changes, or if the ablation/telemetry/GraphRAG-baseline milestones (M6-M8, not run in this stack) are later completed to strengthen a main-track resubmission. It is not the primary target for this M9 pass because its CFP is not yet live and NORA already offers a verified, open, sufficiently-distant deadline.

## Companion: arXiv technical report

Independent of any venue decision, an arXiv technical report can be posted immediately once the submission package (M9 PR-3) is finalized, establishing priority ahead of the fast-moving OKF ecosystem. This does not require a venue-specific template and carries no deadline.

## Summary decision

**Default package target: NORA 2026 @ AACL-IJCNLP, Research Papers track, CEURART template, 8-page budget, deadline 2026-09-09 AoE.** EMNLP Insights stays unselected pending its own CFP. MLSys 2027 Research Track stays the fallback pending its own CFP. An arXiv technical report is prepared as a template-independent companion artifact.
