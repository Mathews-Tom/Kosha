"""Relate eval: cross-link discovery quality against labeled edge sets.

Each case is a small bundle of concepts plus the gold inter-concept edges a good
cross-linker should discover. The relator runs over the bundle and is scored on
precision/recall/F1 of its discovered edges vs the gold set.

Like the other model-backed surfaces (extract/dedup/merge), this discriminates the
deterministic default from a real model: the ``clear`` band — pairs that overlap
lexically and share a tag — is recoverable offline, while an ``ambiguous`` band of
semantically-related but lexically-disjoint pairs leaves recall headroom a
:class:`~kosha.link.relate.GenerationRelator` can close. Offline full-set recall
therefore stays below 1.0 by construction.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from kosha.link.relate import Relator, discover_relations
from kosha.model import Bundle, Concept, Frontmatter


@dataclass(frozen=True)
class RelateCase:
    """A labeled cross-link case: a mini-bundle plus its gold directed edges."""

    bundle: Bundle
    gold: frozenset[tuple[str, str]]
    band: str


@dataclass(frozen=True)
class RelateEvalReport:
    """Aggregate precision/recall/F1 of discovered edges over all cases."""

    case_count: int
    true_positives: int
    predicted: int
    gold_total: int

    @property
    def precision(self) -> float:
        return self.true_positives / self.predicted if self.predicted else 1.0

    @property
    def recall(self) -> float:
        return self.true_positives / self.gold_total if self.gold_total else 1.0

    @property
    def f1(self) -> float:
        denominator = self.precision + self.recall
        return 2 * self.precision * self.recall / denominator if denominator else 0.0


def load_relate_cases(path: Path) -> list[RelateCase]:
    """Load relate cases from a JSONL file (one case per line)."""
    cases: list[RelateCase] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        cases.append(_case_from_record(json.loads(line)))
    return cases


def evaluate_relate(cases: Iterable[RelateCase], relator: Relator) -> RelateEvalReport:
    """Grade ``relator``'s discovered edges against each case's gold edge set."""
    case_count = true_positives = predicted = gold_total = 0
    for case in cases:
        case_count += 1
        discovered = {(r.source, r.target) for r in discover_relations(case.bundle, relator)}
        true_positives += len(discovered & case.gold)
        predicted += len(discovered)
        gold_total += len(case.gold)
    return RelateEvalReport(
        case_count=case_count,
        true_positives=true_positives,
        predicted=predicted,
        gold_total=gold_total,
    )


def _case_from_record(record: dict[str, object]) -> RelateCase:
    raw_concepts = record.get("concepts")
    if not isinstance(raw_concepts, list):
        raise ValueError("relate case is missing a 'concepts' list")
    concepts = [_concept_from_record(item) for item in raw_concepts]
    bundle = Bundle(root_path="eval://relate", concepts={c.concept_id: c for c in concepts})
    gold = {
        (source, target)
        for source, targets in _require_edges(record).items()
        for target in targets
    }
    band = record.get("band")
    return RelateCase(
        bundle=bundle,
        gold=frozenset(gold),
        band=band if isinstance(band, str) else "",
    )


def _concept_from_record(item: object) -> Concept:
    if not isinstance(item, dict):
        raise ValueError("each concept must be a JSON object")
    tags = item.get("tags")
    frontmatter = Frontmatter(
        type=_text(item, "type", default="Concept"),
        title=_text(item, "title", default="") or None,
        description=_text(item, "description", default="") or None,
        tags=[tag for tag in tags if isinstance(tag, str)] if isinstance(tags, list) else [],
    )
    return Concept(
        concept_id=_text(item, "id"),
        frontmatter=frontmatter,
        body=_text(item, "body", default=""),
    )


def _require_edges(record: dict[str, object]) -> dict[str, list[str]]:
    edges = record.get("edges", {})
    if not isinstance(edges, dict):
        raise ValueError("relate case 'edges' must be an object")
    return {
        source: [target for target in targets if isinstance(target, str)]
        for source, targets in edges.items()
        if isinstance(targets, list)
    }


def _text(item: dict[str, object], key: str, *, default: str | None = None) -> str:
    value = item.get(key)
    if isinstance(value, str):
        return value
    if default is not None:
        return default
    raise ValueError(f"concept field {key!r} must be a string")
