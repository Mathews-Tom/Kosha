"""Contradict eval: conflict-detection quality against labeled claim pairs.

The contradiction surface (system_design §4.3.1) is judged like the other LLM
surfaces — measured, not assumed. Each labeled case is a prior/new claim pair
tagged ``conflict`` (a material contradiction) or ``none`` (a restatement,
refinement, or unrelated addition). :func:`evaluate_contradict` runs a
:class:`~kosha.contradiction.detect.ContradictionJudge` over the pairs and scores
precision/recall/F1 on the ``conflict`` class.

The ``clear`` band — value or polarity divergence on a shared subject — the
offline :class:`~kosha.contradiction.detect.LexicalContradictionJudge` resolves
perfectly. The ``ambiguous`` band — a conflict the structured-diff signals miss —
is the headroom a real model closes, the same "could a prompt do it?" gap the
dedup eval documents.

Every case also carries a ``regime`` — the semantic shape of the conflict, one of
``numeric``, ``negation``, ``unit``, ``partial``, ``temporal``, ``adversarial``
(plus ``restatement``/``unrelated`` for compatible pairs). ``clear``-band regime
is derived from the structured-diff signal (it is already what the deterministic
detector keys on); ``ambiguous``-band regime is labeled explicitly, since those
are exactly the cases the structured signals cannot classify. Gate-0 v2 (M3)
measures the judge per regime so the subtle-regime headroom the S2 report
diagnosed (unit/partial/temporal/adversarial) is visible, not averaged away.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from kosha.contradiction.detect import (
    ContradictionJudge,
    ContradictionVerdict,
    DiffSignal,
    structured_diff,
)

_CONFLICT = "conflict"
_NONE = "none"
_LABELS = (_CONFLICT, _NONE)
_CLEAR = "clear"
_AMBIGUOUS = "ambiguous"
_BANDS = (_CLEAR, _AMBIGUOUS)
_AMBIGUOUS_REGIMES = frozenset({"numeric", "unit", "partial", "temporal", "adversarial"})


@dataclass(frozen=True)
class ContradictCase:
    """A labeled prior/new claim pair for conflict-detection evaluation."""

    old: str
    new: str
    label: str
    band: str
    regime: str


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
        band = _require_str(record, "band")
        if band not in _BANDS:
            raise ValueError(f"{path}: band must be one of {_BANDS}, got {band!r}")
        old = _require_str(record, "old")
        new = _require_str(record, "new")
        cases.append(
            ContradictCase(
                old=old,
                new=new,
                label=label,
                band=band,
                regime=_resolve_regime(record, path, band, old, new),
            )
        )
    return cases


def _resolve_regime(
    record: dict[str, object], path: Path, band: str, old: str, new: str
) -> str:
    """Return the case's conflict regime: explicit for ``ambiguous``, derived for ``clear``.

    ``clear``-band regime is derived from the same structured-diff signal the
    deterministic detector already keys on, so authoring a clear-band case never
    requires a separate regime label. ``ambiguous``-band cases are exactly the
    ones the structured signals cannot classify, so their regime is labeled
    explicitly and validated against the six-regime taxonomy (S2 gate2-report).
    """
    if band == _AMBIGUOUS:
        regime = _require_str(record, "regime")
        if regime not in _AMBIGUOUS_REGIMES:
            raise ValueError(
                f"{path}: ambiguous regime must be one of {sorted(_AMBIGUOUS_REGIMES)}, "
                f"got {regime!r}"
            )
        return regime
    return _clear_regime(structured_diff(old, new))


def _clear_regime(signal: DiffSignal) -> str:
    if signal.identical:
        return "restatement"
    if signal.numeric_conflict:
        return "numeric"
    if signal.negation_conflict:
        return "negation"
    return "unrelated"


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


def evaluate_contradict_by_regime(
    cases: Iterable[ContradictCase], judge: ContradictionJudge
) -> dict[str, ContradictEvalReport]:
    """Grade ``judge`` per regime so subtle-regime headroom is visible per bucket.

    Averaging across the whole corpus hides exactly the gap Gate-0 v2 measures:
    the judge can be strong on ``numeric``/``negation`` (the clear band) while
    losing on ``unit``/``partial``/``temporal``/``adversarial`` (the S2-diagnosed
    subtle regimes). Reporting per regime keeps that gap visible.
    """
    by_regime: dict[str, list[ContradictCase]] = {}
    for case in cases:
        by_regime.setdefault(case.regime, []).append(case)
    return {
        regime: evaluate_contradict(regime_cases, judge)
        for regime, regime_cases in sorted(by_regime.items())
    }


def _require_str(record: dict[str, object], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str):
        raise ValueError(f"field {key!r} must be a string")
    return value
