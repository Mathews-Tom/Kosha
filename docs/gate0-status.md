# Gate-0 Status

Kosha has two separate evidence tracks. The deterministic local-provider gates verify reproducible mechanics on the bundled reference corpus. The real-model Gate-0 runs test whether the maintenance loop beats a strong prompt-only baseline on decision quality.

> Maintenance note (M3): the "Current public verdict" sentence and each evidence-table row below must be generated, not hand-authored. After a Gate-0 run, call `render_gate_status_summary`/`render_gate_status_row` from `kosha.bench.realworld.status` on the resulting `RealworldReport` and paste the output here verbatim — `tests/bench/test_realworld_status.py::test_gate0_status_doc_matches_the_current_recorded_verdict` fails the build if this file drifts from what the renderer would produce for the currently recorded verdict.

## Current public verdict

<!-- kosha:sync:start gate0-status -->
**Real-model Gate-0 verdict: NO-GO.** Kosha ships as an OSS governance skill. M14+ product expansion remains halted unless a later pre-registered real-model Gate-0 run records a GO verdict.
<!-- kosha:sync:end -->

## Evidence summary

| Run | Setup | Result |
|---|---|---|
| M13 Gate-0 (`276d240`, 2026-06-29) | bge-m3 + gpt-4o-mini, 680-concept `pydoc-stdlib`, 50 sequential ingests | **NO-GO** — maintenance accuracy 0.50 vs prompt-only 0.79; contradiction routing 0.17 vs 1.00 |
| M13 reframed (`52f1fdf`, 2026-06-29) | Same corpus and provider, safety-margin criterion | **NO-GO** — safety tied prompt-only at 1.00 vs 1.00, below the required +0.25 margin; routing reached parity after S1 but did not reopen Gate 0 |
| S2 Gate-0 v2 (`3b46983`, 2026-06-29) | 2 embeddings × 2 generation models × 3 runs, 108 held-out contradictions across 6 regimes; cross-vendor smoke with llama-3.3-70b | **NO-GO** — loop detection and safety trailed prompt-only by 0.28–0.33 on every provider cell; M14+ stays halted |
| S2-v3 Gate-0 (`edbe91b`, 2026-07-09) | openai:bge-m3 + generation matrix {openai:gpt-4.1-nano, qwen:qwen3-235b-a22b-2507}, 2-concept corpus, 50 sequential ingests/cell | **NO-GO** — both cells had 0 held-out contradiction cases; OpenAI cell preserved drift maintenance accuracy 1.00 -> 1.00, Qwen cell regressed 1.00 -> 0.00; loop silent overwrites 0 |

S2-v3 now exercises the pre-registered second, non-Python-docs corpus (`bundles/paper-s2v3-corpus`) with two real OpenRouter generation models from different vendors: `openai/gpt-4.1-nano` and `qwen/qwen3-235b-a22b-2507`. The provider-matrix shape is satisfied, but the held-out sample remains thin: 1 held-out query and 0 contradiction cases per cell, so the 0.00 safety rate reflects an empty sample rather than a measured loss. The stricter rerun is recorded here as a NO-GO evidence artifact: the OpenAI cell preserved maintenance accuracy across drift, the Qwen cell regressed maintenance accuracy from 1.00 to 0.00, and neither cell supports a decision-quality or retrieval-superiority claim. The prior S2 Gate-0 v2 matrix over 108 held-out contradictions remains the operative safety evidence.

## Boundary of the claim

Kosha's verified differentiator is the governance guarantee: zero silent overwrites across the S2 and S2-v3 runs, replayable claim lineage, and branch-per-ingest provenance. That guarantee is real and prompt-only baselines do not provide an equivalent audit trail.

Kosha does **not** currently claim decision-quality superiority over a good prompt. The real-model Gate-0 runs found the opposite for the measured decision-quality axes. Future work can attempt to reopen Gate 0, but production-loop expansion stays halted until the pre-registered criterion records a GO. S2-v3's stricter second-corpus provider-matrix rerun did not change this boundary.

Kosha does **not** currently claim retrieval superiority over real-world RAG systems. The deterministic hybrid-vs-RAG numbers are internal self-consistency checks on toy providers, not a real-model superiority claim. S2-v3's single held-out query per real-provider cell is too small a sample to support a retrieval claim either.

Kosha also does **not** claim that a host agent with generic filesystem tools is unable to search files. The shipped MCP server exposes traversal tools and no raw-text search endpoint. The file-based fallback gives traversal instructions. Only a future sandboxed serving boundary can enforce that the agent's filesystem access terminates at Kosha.
