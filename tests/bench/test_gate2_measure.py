"""The Gate-0 v2 per-cell measurement: dual axes over the held-out set (spike S2)."""

from __future__ import annotations

from pathlib import Path

from kosha.bench.gate2.criterion import REGIMES
from kosha.bench.realworld import RealworldConfig, build_gate2_measure
from kosha.providers import ExtractiveGenerationProvider, LexicalEmbeddingProvider

ROOT = Path(__file__).resolve().parents[2]


def _config() -> RealworldConfig:
    return RealworldConfig(
        corpus=ROOT / "bundles" / "pydoc-stdlib",
        queries=ROOT / "evals" / "realworld" / "queries.jsonl",
        maintenance=ROOT / "evals" / "realworld" / "maintenance.jsonl",
        guidance=ROOT / "consumer" / "AGENTS.fragment.md",
        contradictions=ROOT / "evals" / "realworld" / "contradictions_v2.jsonl",
        candidate_k=4,
    )


def test_measure_reports_both_axes_over_the_powered_held_out_set() -> None:
    measure = build_gate2_measure(_config())
    sample = measure(LexicalEmbeddingProvider(), ExtractiveGenerationProvider())
    assert tuple(axis.axis for axis in sample.axes) == ("detection_recall", "safety_rate")
    assert sample.contradictions >= 100
    assert sample.regimes == REGIMES
    assert sample.loop_silent_overwrites == 0


def test_detector_gate_gives_the_loop_offline_detection() -> None:
    # With an offline (extractive) judge the prompt-only baseline detects nothing,
    # but the code-owned detector still catches the numeric/negation conflicts:
    # the loop's structural edge is visible even without a real LLM.
    measure = build_gate2_measure(_config())
    sample = measure(LexicalEmbeddingProvider(), ExtractiveGenerationProvider())
    detection = next(axis for axis in sample.axes if axis.axis == "detection_recall")
    assert detection.loop > 0.0
    assert detection.loop >= detection.prompt


def test_runs_replay_across_embeddings_when_runs_per_cell_set() -> None:
    # The quality axes are embedding-independent, so a later embedding cell replays
    # the generation's runs instead of re-calling the LLM to the same effect.
    measure = build_gate2_measure(_config(), runs_per_cell=2)
    embed_a, embed_b = LexicalEmbeddingProvider(), LexicalEmbeddingProvider()
    gen = ExtractiveGenerationProvider()
    a0, a1 = measure(embed_a, gen), measure(embed_a, gen)
    b0, b1 = measure(embed_b, gen), measure(embed_b, gen)
    assert b0 is a0
    assert b1 is a1


def test_no_runs_per_cell_recomputes_each_call() -> None:
    measure = build_gate2_measure(_config())
    embed = LexicalEmbeddingProvider()
    gen = ExtractiveGenerationProvider()
    first, second = measure(embed, gen), measure(embed, gen)
    # Distinct objects: no replay cache when runs_per_cell is unset.
    assert first is not second
