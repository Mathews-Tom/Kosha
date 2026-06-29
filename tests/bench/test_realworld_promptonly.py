"""Offline tests for the prompt-only baseline (stubbed generation, real embedding).

Only generation is stubbed; the embedding jump uses the real lexical provider over
the golden corpus, so candidate selection and the parse/score plumbing are
exercised without a network call.
"""

from __future__ import annotations

from pathlib import Path

from kosha.bench.realworld.promptonly import (
    PromptOnlyBaseline,
    _parse_cited,
    _parse_decision,
)
from kosha.index import EmbeddingIndex
from kosha.okf import load_bundle
from kosha.providers import LexicalEmbeddingProvider
from kosha.providers.base import Generation, Usage
from kosha.providers.tokens import count_tokens

NORTHWIND = Path(__file__).resolve().parents[2] / "bundles" / "northwind"
_GUIDANCE = "Traverse the bundle; cite the concept ids you use."


class _StubGenerator:
    """A deterministic generation provider that returns a fixed reply."""

    def __init__(self, reply: str) -> None:
        self._reply = reply
        self.calls: list[tuple[str, str]] = []

    @property
    def name(self) -> str:
        return "stub"

    def generate(self, query: str, context: str) -> Generation:
        self.calls.append((query, context))
        usage = Usage(
            prompt_tokens=count_tokens(query) + count_tokens(context),
            completion_tokens=count_tokens(self._reply),
        )
        return Generation(text=self._reply, usage=usage)


def _baseline(reply: str) -> PromptOnlyBaseline:
    bundle = load_bundle(NORTHWIND)
    index = EmbeddingIndex.build(bundle, LexicalEmbeddingProvider())
    return PromptOnlyBaseline(bundle, index, _StubGenerator(reply), guidance=_GUIDANCE)


def test_answer_scores_candidates_and_reports_citations_separately() -> None:
    baseline = _baseline("Gold members get 45 days. CITED: policies/returns/gold-members")
    result = baseline.answer("How long does a gold member have to return an item?")
    # Concept recall is scored over the loaded candidates (the embedding jump),
    # which the runner grades; the model's citation is reported separately and
    # never folded into recall.
    assert result.context.concept_ids
    candidates = baseline._candidates("How long does a gold member have to return an item?")
    assert list(result.context.concept_ids) == candidates
    assert result.cited == ("policies/returns/gold-members",)
    assert result.context.round_trips == 1
    assert result.generation.usage.total_tokens > 0


def test_answer_passes_guidance_and_instruction_to_the_model() -> None:
    baseline = _baseline("CITED: policies/refunds")
    baseline.answer("How long do refunds take?")
    generator = baseline._generator
    assert isinstance(generator, _StubGenerator)
    query, _context = generator.calls[0]
    assert _GUIDANCE in query
    assert "CITED" in query


def test_route_parses_update_to_an_existing_concept() -> None:
    baseline = _baseline("UPDATE policies/returns/standard")
    decision = baseline.route("Standard returns", "Standard returns accepted within 30 days.")
    assert decision.action == "UPDATE"
    assert decision.concept_id == "policies/returns/standard"


def test_route_parses_create_for_new_knowledge() -> None:
    baseline = _baseline("CREATE")
    decision = baseline.route("Loyalty points", "Customers earn one point per dollar spent.")
    assert decision.action == "CREATE"
    assert decision.concept_id is None


def test_parse_cited_filters_unknown_ids() -> None:
    valid = {"policies/refunds", "policies/shipping"}
    cited = _parse_cited("Answer.\nCITED: policies/refunds, made/up, policies/shipping", valid)
    assert cited == ["policies/refunds", "policies/shipping"]


def test_parse_decision_rejects_unknown_update_target() -> None:
    decision = _parse_decision("UPDATE not/a/real/concept", {"policies/refunds"})
    assert decision.action == "UPDATE"
    assert decision.concept_id is None


def test_parse_decision_defaults_to_create_when_unparseable() -> None:
    decision = _parse_decision("I am not sure what to do here.", {"policies/refunds"})
    assert decision.action == "CREATE"
    assert decision.concept_id is None


def test_candidate_k_must_be_positive() -> None:
    bundle = load_bundle(NORTHWIND)
    index = EmbeddingIndex.build(bundle, LexicalEmbeddingProvider())
    try:
        PromptOnlyBaseline(bundle, index, _StubGenerator(""), guidance="g", candidate_k=0)
    except ValueError:
        return
    raise AssertionError("expected ValueError for candidate_k=0")
