"""Dedup eval: precision/recall over labeled pairs + repeated-ingest duplicate rate.

Two measurements back the dedup loop (overview §6, DEVELOPMENT_PLAN M6):

* :func:`evaluate_dedup` runs the full resolver over the seed pairs — treating
  pair ``a`` as the sole existing concept and ``b`` as the incoming draft — and
  scores UPDATE-as-"same" against the labels (precision/recall on the same
  class). The clear band resolves well; the ambiguous band is where a real model
  earns its keep over the offline lexical adjudicator — the documented dedup
  headroom a single threshold cannot close (overview §6).
* :func:`evaluate_duplicate_rate` re-ingests a bundle's own concepts against an
  index built from it. With the draft-to-index text parity every concept
  self-matches and updates, so the duplicate rate is ~0 — the M6 success contract.
"""

from __future__ import annotations

from dataclasses import dataclass

from kosha.bench import DedupPair
from kosha.dedup import (
    DEFAULT_THRESHOLDS,
    Action,
    Adjudicator,
    Thresholds,
    resolve_draft,
)
from kosha.extract import ConceptDraft
from kosha.index import EmbeddingIndex
from kosha.index.embedding import index_text
from kosha.model import Bundle
from kosha.providers.base import EmbeddingProvider

_SAME = "same"


@dataclass(frozen=True)
class DedupEvalReport:
    """Precision/recall of the resolver's same-vs-different calls over the pairs."""

    pair_count: int
    true_positive: int
    false_positive: int
    false_negative: int
    true_negative: int

    @property
    def precision(self) -> float:
        denominator = self.true_positive + self.false_positive
        return self.true_positive / denominator if denominator else 1.0

    @property
    def recall(self) -> float:
        denominator = self.true_positive + self.false_negative
        return self.true_positive / denominator if denominator else 1.0

    @property
    def accuracy(self) -> float:
        if not self.pair_count:
            return 1.0
        return (self.true_positive + self.true_negative) / self.pair_count


@dataclass(frozen=True)
class DuplicateRateReport:
    """Outcome of re-ingesting a bundle's own concepts against its index."""

    concept_count: int
    created: int
    updated: int

    @property
    def duplicate_rate(self) -> float:
        return self.created / self.concept_count if self.concept_count else 0.0


def evaluate_dedup(
    pairs: list[DedupPair],
    embedding_provider: EmbeddingProvider,
    *,
    adjudicator: Adjudicator,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
) -> DedupEvalReport:
    """Score the resolver's UPDATE(=same)/CREATE(=different) calls on the pairs."""
    if not pairs:
        raise ValueError("no dedup pairs to evaluate")
    tp = fp = fn = tn = 0
    for pair in pairs:
        candidate_vector = embedding_provider.embed([pair.a])[0]
        index = EmbeddingIndex(embedding_provider, {"candidate": candidate_vector})
        draft = ConceptDraft(
            title="incoming", body=pair.b, description="", type="concept", source_id="eval://dedup"
        )
        decision = resolve_draft(
            draft,
            index,
            {"candidate": pair.a},
            adjudicator=adjudicator,
            thresholds=thresholds,
            k=1,
        )
        predicted_same = decision.action is Action.UPDATE
        gold_same = pair.label == _SAME
        if predicted_same and gold_same:
            tp += 1
        elif predicted_same and not gold_same:
            fp += 1
        elif not predicted_same and gold_same:
            fn += 1
        else:
            tn += 1
    return DedupEvalReport(len(pairs), tp, fp, fn, tn)


def evaluate_duplicate_rate(
    bundle: Bundle,
    embedding_provider: EmbeddingProvider,
    *,
    adjudicator: Adjudicator,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
) -> DuplicateRateReport:
    """Re-ingest ``bundle``'s concepts against its own index; count CREATE vs UPDATE."""
    index = EmbeddingIndex.build(bundle, embedding_provider)
    concept_texts = {cid: index_text(concept) for cid, concept in bundle.concepts.items()}
    created = updated = 0
    for concept in bundle.concepts.values():
        draft = ConceptDraft(
            title=concept.frontmatter.title or concept.concept_id,
            body=concept.body,
            description=concept.frontmatter.description or "",
            type=concept.frontmatter.type,
            source_id=f"reingest://{concept.concept_id}",
        )
        decision = resolve_draft(
            draft, index, concept_texts, adjudicator=adjudicator, thresholds=thresholds
        )
        if decision.action is Action.CREATE:
            created += 1
        elif decision.action is Action.UPDATE:
            updated += 1
    return DuplicateRateReport(len(bundle.concepts), created, updated)
