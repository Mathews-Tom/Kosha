"""Contradict eval: conflict-detection quality against labeled claim pairs.

The contradiction surface (system_design §4.3.1) is judged like the other LLM
surfaces — measured, not assumed. Each labeled case is a prior/new claim pair
tagged ``conflict`` (a material contradiction) or ``none`` (a restatement,
refinement, or unrelated addition). :func:`evaluate_contradict` runs a
:class:`~kosha.contradiction.detect.ContradictionJudge` over the pairs and scores
precision/recall/F1 on the ``conflict`` class.

The ``clear`` band — value or polarity divergence on a shared subject — the
offline :class:`~kosha.contradiction.detect.LexicalContradictionJudge` resolves
perfectly. The ``ambiguous`` band — a conflict paraphrased away from any numeric
or negation cue — is the headroom a real model closes, the same "could a prompt
do it?" gap the dedup eval documents.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from kosha.contradiction.detect import ContradictionJudge, ContradictionVerdict, structured_diff

_CONFLICT = "conflict"
_NONE = "none"
_LABELS = (_CONFLICT, _NONE)


@dataclass(frozen=True)
class ContradictCase:
    """A labeled prior/new claim pair for conflict-detection evaluation."""

    old: str
    new: str
    label: str
    band: str


@dataclass(frozen=True)
class ContradictEvalReport:
    """Confusion-matrix precision/recall/F1 on the ``conflict`` class."""

    case_count: int
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int

    @property
    def precision(self) -> float:
        denominator = self.true_positives + self.false_positives
        return self.true_positives / denominator if denominator else 1.0

    @property
    def recall(self) -> float:
        denominator = self.true_positives + self.false_negatives
        return self.true_positives / denominator if denominator else 1.0

    @property
    def f1(self) -> float:
        denominator = self.precision + self.recall
        return 2 * self.precision * self.recall / denominator if denominator else 0.0

    @property
    def accuracy(self) -> float:
        if not self.case_count:
            return 1.0
        return (self.true_positives + self.true_negatives) / self.case_count


def load_contradict_cases(path: Path) -> list[ContradictCase]:
    """Load contradiction cases from a JSONL file (one case per line)."""
    cases: list[ContradictCase] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        record = json.loads(stripped)
        if not isinstance(record, dict):
            raise ValueError(f"{path}: each line must be a JSON object")
        label = _require_str(record, "label")
        if label not in _LABELS:
            raise ValueError(f"{path}: label must be one of {_LABELS}, got {label!r}")
        cases.append(
            ContradictCase(
                old=_require_str(record, "old"),
                new=_require_str(record, "new"),
                label=label,
                band=_require_str(record, "band"),
            )
        )
    return cases


def evaluate_contradict(
    cases: Iterable[ContradictCase], judge: ContradictionJudge
) -> ContradictEvalReport:
    """Grade ``judge``'s conflict calls against the labeled cases."""
    case_count = tp = fp = fn = tn = 0
    for case in cases:
        case_count += 1
        signal = structured_diff(case.old, case.new)
        predicted_conflict = judge.judge(case.old, case.new, signal).verdict is (
            ContradictionVerdict.CONFLICT
        )
        labeled_conflict = case.label == _CONFLICT
        if labeled_conflict and predicted_conflict:
            tp += 1
        elif labeled_conflict and not predicted_conflict:
            fn += 1
        elif not labeled_conflict and predicted_conflict:
            fp += 1
        else:
            tn += 1
    if not case_count:
        raise ValueError("no contradiction cases to evaluate")
    return ContradictEvalReport(
        case_count=case_count,
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        true_negatives=tn,
    )


def _require_str(record: dict[str, object], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str):
        raise ValueError(f"field {key!r} must be a string")
    return value
