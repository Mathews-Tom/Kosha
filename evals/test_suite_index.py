"""Eval suite index: one runnable suite per LLM surface (overview §6, M12).

The maintenance-loop moat is "a rigorous eval harness — one suite per LLM
surface" (overview §6). This index is the single source of truth for that set:
every model-backed surface of the loop must have a collected eval suite, and
every eval suite must score a real surface. `uv run pytest evals -q` runs them
all; this module fails CI if a surface ever loses its suite or an orphan suite
appears, so the consolidation cannot silently rot.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import kosha.eval as eval_module

EVALS_ROOT = Path(__file__).resolve().parent

# One eval suite per model-backed surface of the maintenance loop, mapped to the
# eval entrypoint in `kosha.eval` it exercises.
LLM_SURFACES: dict[str, str] = {
    "extract": "evaluate_extractor",
    "dedup": "evaluate_dedup",
    "merge": "evaluate_merge",
    "relate": "evaluate_relate",
    "contradict": "evaluate_contradict",
}


@pytest.mark.parametrize("surface", sorted(LLM_SURFACES))
def test_each_surface_has_a_runnable_suite(surface: str) -> None:
    suite = EVALS_ROOT / surface / f"test_{surface}_eval.py"
    assert suite.is_file(), f"missing eval suite for the {surface} surface"
    assert "def test_" in suite.read_text(encoding="utf-8")


@pytest.mark.parametrize("surface, entrypoint", sorted(LLM_SURFACES.items()))
def test_each_surface_maps_to_an_eval_entrypoint(surface: str, entrypoint: str) -> None:
    assert hasattr(eval_module, entrypoint), (
        f"the {surface} surface has no {entrypoint} entrypoint in kosha.eval"
    )


def test_no_orphan_or_missing_suite() -> None:
    present = {suite.parent.name for suite in EVALS_ROOT.glob("*/test_*_eval.py")}
    assert present == set(LLM_SURFACES)
