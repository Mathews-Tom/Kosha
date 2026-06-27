"""Seed dedup/granularity labels and the threshold-only dedup baseline.

The seed labels are the first slice of the eval-data the moat depends on
(overview §6, §8). Two evaluations run against them:

* :func:`evaluate_threshold_only` — the "could a prompt do it?" dedup baseline:
  classify each labeled pair as same/different by a single cosine-similarity
  threshold. If the best threshold cannot separate the set (an ambiguous band
  remains), the dedup loop's LLM adjudication has headroom a prompt does not close.
* :func:`evaluate_granularity` — whether the granularity lint flags the
  over-scoped examples and leaves the atomic ones alone.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from kosha.lint import granularity_warnings
from kosha.providers.base import EmbeddingProvider, Vector

_SAME = "same"
_AMBIGUOUS = "ambiguous"
_OVERSCOPED = "overscoped"


@dataclass(frozen=True)
class DedupPair:
    """A labeled concept-statement pair for dedup evaluation."""

    a: str
    b: str
    label: str
    band: str


@dataclass(frozen=True)
class GranularityLabel:
    """A labeled concept body for granularity evaluation."""

    text: str
    label: str


@dataclass(frozen=True)
class DedupSignal:
    """Outcome of the threshold-only dedup baseline over the seed pairs."""

    pair_count: int
    ambiguous_count: int
    best_threshold: float
    best_accuracy: float
    ambiguous_errors: int


@dataclass(frozen=True)
class GranularitySignal:
    """Outcome of the granularity lint over the seed labels."""

    label_count: int
    correct: int

    @property
    def accuracy(self) -> float:
        return self.correct / self.label_count if self.label_count else 1.0


def load_dedup_pairs(path: Path) -> list[DedupPair]:
    """Load dedup pairs from a JSONL file."""
    pairs: list[DedupPair] = []
    for record in _read_jsonl(path):
        pairs.append(
            DedupPair(
                a=_require_str(record, "a"),
                b=_require_str(record, "b"),
                label=_require_str(record, "label"),
                band=_require_str(record, "band"),
            )
        )
    return pairs


def load_granularity_labels(path: Path) -> list[GranularityLabel]:
    """Load granularity labels from a JSONL file."""
    labels: list[GranularityLabel] = []
    for record in _read_jsonl(path):
        labels.append(
            GranularityLabel(
                text=_require_str(record, "text"),
                label=_require_str(record, "label"),
            )
        )
    return labels


def evaluate_threshold_only(
    pairs: list[DedupPair], provider: EmbeddingProvider
) -> DedupSignal:
    """Score the best single cosine threshold against the labeled pairs."""
    if not pairs:
        raise ValueError("no dedup pairs to evaluate")
    sims = [_cosine(*provider.embed([pair.a, pair.b])) for pair in pairs]
    is_same = [pair.label == _SAME for pair in pairs]
    candidates = sorted({*sims, min(sims) - 1e-6, max(sims) + 1e-6})
    best_threshold = candidates[0]
    best_accuracy = -1.0
    for threshold in candidates:
        correct = sum(
            (sim >= threshold) == same for sim, same in zip(sims, is_same, strict=True)
        )
        accuracy = correct / len(pairs)
        if accuracy > best_accuracy:
            best_accuracy = accuracy
            best_threshold = threshold
    ambiguous_errors = sum(
        1
        for sim, pair in zip(sims, pairs, strict=True)
        if pair.band == _AMBIGUOUS
        and (sim >= best_threshold) != (pair.label == _SAME)
    )
    return DedupSignal(
        pair_count=len(pairs),
        ambiguous_count=sum(1 for pair in pairs if pair.band == _AMBIGUOUS),
        best_threshold=best_threshold,
        best_accuracy=best_accuracy,
        ambiguous_errors=ambiguous_errors,
    )


def evaluate_granularity(labels: list[GranularityLabel]) -> GranularitySignal:
    """Score the granularity lint's over-scoped/atomic calls against labels."""
    correct = 0
    for label in labels:
        predicted_overscoped = bool(granularity_warnings(label.text))
        if predicted_overscoped == (label.label == _OVERSCOPED):
            correct += 1
    return GranularitySignal(label_count=len(labels), correct=correct)


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parsed = json.loads(stripped)
        if not isinstance(parsed, dict):
            raise ValueError(f"{path}: each line must be a JSON object")
        records.append(parsed)
    return records


def _require_str(record: dict[str, object], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str):
        raise ValueError(f"missing or non-string field {key!r}")
    return value


def _cosine(a: Vector, b: Vector) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = (sum(x * x for x in a) ** 0.5) * (sum(y * y for y in b) ** 0.5)
    return dot / norm if norm else 0.0
