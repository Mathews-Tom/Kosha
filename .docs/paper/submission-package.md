# Submission Package

This document freezes the M9 submission-readiness package: the venue checklist, the citation checklist, the artifact checklist, the reviewer-objection matrix status, and the final GO/NO-GO submission verdict. It does not submit to any venue; that step remains a manual, out-of-session action per the milestone's constraints.

## Venue checklist — PASS

Verified live and frozen in `.docs/paper/venue-verification.md`:

| Item | Status |
|---|---|
| Deadline verified live | PASS — NORA 2026 @ AACL-IJCNLP, 2026-09-09 AoE |
| Template verified live | PASS — CEURART, LaTeX or ODT, OpenReview submission |
| Page limit verified live | PASS — Research Papers track, 8 pages excluding references/appendices |
| Artifact/reproducibility rules checked | PASS — no special software-artifact requirement beyond standard supplementary material |

## Citation checklist — PASS

Machine-verified by `tests/docs/test_paper_claims.py`, not just manually reviewed:

- Every citation in `.docs/paper/citations.md` carries a non-empty source identifier (arXiv id, DOI, or named venue) — `test_every_citation_has_a_source_identifier`.
- Every required closest-prior-work citation (VMG, Zep/Graphiti, MemOS, Wikidata bot approval, Saga, GraphRAG, RAG) is present — `test_citation_inventory_covers_required_closest_priors`.
- Every arXiv id used in `.docs/paper/related-work.md` prose resolves to an inventory entry — `test_every_related_work_citation_is_in_the_inventory`.
- No unchecked citation remains: the four load-bearing, highest-novelty-risk citations (VMG arXiv:2604.16548, Zep/Graphiti arXiv:2501.13956, MemOS arXiv:2505.22101, GraphRAG arXiv:2404.16130) were independently spot-verified via live search during M5, corroborating the source literature review's stated verification methodology.

## Artifact checklist — PASS

Every numeric claim in the paper package resolves to a checked-in report or a byte-reproducible command, machine-verified by `tests/docs/test_paper_claims.py::test_every_evidence_ledger_claim_links_to_a_checked_in_source`:

- Deterministic self-consistency: `ACCEPTANCE_REPORT.md`, reproduced by `uv run kosha bench acceptance --report ACCEPTANCE_REPORT.md`.
- Real-model Gate-0 (M13/S2): `docs/gate0-status.md`, generated (not hand-authored) from `kosha.bench.realworld.status` renderers, doc-drift CI-gated by `tests/bench/test_realworld_status.py`.
- S2-v3 second-corpus, cross-vendor (M3): `.docs/s2-v3-report.md`, `.docs/s2-v3-preregistration.md`.
- Real-model fidelity (M4): `.docs/real-model-fidelity-report.md`.
- Evidence ledger, citation inventory, related work, experiments/reproducibility, draft, positioning notes: `.docs/paper/`.

Reproduction instructions separate deterministic offline commands (exercised in CI on every PR) from paid real-provider commands (reviewed provider env, checked-in reports, qualitative-not-exact reproducibility) — `.docs/paper/experiments-and-reproducibility.md` section E.

## Reviewer-objection matrix — complete

`.docs/paper/reviewer-objection-matrix.md` answers every challenge that survived the original adversarial literature review, plus every objection raised by evidence produced since (M3, M4). No objection is left unanswered or answered by an unsupported claim; limitations are stated directly (S2-v3 sample size, single-model fidelity run, NORA's KG-framing partial mismatch, M6-M8's absence).

## Does S2-v3 generalize the negative result, or change the story?

**S2-v3 generalizes the negative result.** The pre-registered decision rule (`.docs/paper/draft.md` section 5) stated that a NO-GO on S2-v3 keeps the paper a generalized negative-results paper, while a GO would have pivoted the framing to conditional-autonomy findings. S2-v3 returned NO-GO on both cross-vendor cells (`.docs/s2-v3-report.md`), so the paper's final shape is the generalized negative result: across two corpora and multiple generation-model vendors, the LLM-in-the-loop maintenance pipeline does not currently beat a well-instructed prompt-only baseline, and this is not an artifact of a single corpus or model family.

## Final paper package

| Component | Path |
|---|---|
| Assembled draft (abstract, intro, mechanism, methodology, results, limitations, conclusion) | `.docs/paper/draft.md` |
| Related work | `.docs/paper/related-work.md` |
| Experiments and reproducibility | `.docs/paper/experiments-and-reproducibility.md` |
| Evidence ledger | `.docs/paper/evidence-ledger.md` |
| Citation inventory | `.docs/paper/citations.md` |
| Positioning notes and contribution/non-claim table | `.docs/paper-positioning.md` |
| Venue verification | `.docs/paper/venue-verification.md` |
| Reviewer-objection matrix | `.docs/paper/reviewer-objection-matrix.md` |
| Public verdict status (generated, doc-drift CI-gated) | `docs/gate0-status.md` |

## arXiv technical-report readiness note

The assembled draft (`.docs/paper/draft.md`) and its component documents are template-independent prose, not LaTeX for any specific venue. Before an arXiv post: convert to the arXiv-preferred format (LaTeX or PDF via any standard toolchain), retain every evidence cross-link as a citation or footnote to the checked-in report paths, and keep the non-claim boxes and required disclosures intact — arXiv carries no page limit or template constraint, so no content needs to be cut for that path. An arXiv post can proceed independent of, and prior to, the NORA workshop decision, per `.docs/paper/venue-verification.md`'s companion-artifact note.

## Final submission verdict

**GO.**

Every hard requirement is met: the venue checklist is PASS with a live, verified, two-month-runway deadline; the citation checklist is PASS and machine-enforced; the artifact checklist is PASS with every numeric claim traceable to a checked-in report or reproducible command; the reviewer-objection matrix is complete with no unanswered surviving challenge; and the S2-v3 outcome (generalized negative result) drives the final package framing rather than being interpreted after the fact. No hard requirement is missing, so this does not return NO-GO.

This verdict authorizes the package as submission-ready. It does not submit to NORA, EMNLP, MLSys, or arXiv from this session — that step is a deliberate manual action outside agent scope, consistent with the milestone's constraints.
