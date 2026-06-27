"""Merge eval: claim-targeting accuracy of the body-merge surface.

The merge/writer's one model-backed decision is claim targeting — given an
incoming statement and a concept's in-force claims, which claim (if any) does it
revise (M7 PR-3). This suite scores that call against labeled cases: each case
lists the existing claim statements, an incoming update, and the index of the
claim it revises (``-1`` = a new claim).

As with the dedup eval, the deterministic ``LexicalClaimTargeter`` nails the
``clear`` band (a near-verbatim revision overlaps its claim lexically) but misses
the ``ambiguous`` band — a paraphrase whose wording diverges from the claim it
revises. That gap is the documented headroom a real model closes, so offline
accuracy stays below 1.0 by design.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from kosha.merge.claims import make_claim
from kosha.merge.update import ClaimTargeter
from kosha.model import Claim

# A fixed assertion time: claim ids only need to be stable within a case.
_SEED_TIME = datetime(2026, 1, 1, tzinfo=UTC)
# Sentinel target meaning "no existing claim is revised" (a new claim).
NOVEL = -1


@dataclass(frozen=True)
class MergeCase:
    """A labeled claim-targeting case."""

    existing: tuple[str, ...]
    update: str
    target: int
    band: str


@dataclass(frozen=True)
class MergeEvalCase:
    """The graded outcome for one targeting case."""

    band: str
    expected: int
    predicted: int
    correct: bool


@dataclass(frozen=True)
class MergeEvalReport:
    """The merge eval outcome over the whole case set."""

    case_count: int
    correct: int
    cases: tuple[MergeEvalCase, ...]

    @property
    def score(self) -> float:
        """Fraction of cases whose targeting the surface called correctly."""
        return self.correct / self.case_count if self.case_count else 1.0


def load_merge_cases(path: Path) -> list[MergeCase]:
    """Load claim-targeting cases from a JSONL file."""
    cases: list[MergeCase] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        record = json.loads(stripped)
        if not isinstance(record, dict):
            raise ValueError(f"{path}: each line must be a JSON object")
        cases.append(
            MergeCase(
                existing=tuple(_require_str_list(record, "existing")),
                update=_require_str(record, "update"),
                target=_require_int(record, "target"),
                band=_require_str(record, "band"),
            )
        )
    return cases


def evaluate_merge(cases: list[MergeCase], targeter: ClaimTargeter) -> MergeEvalReport:
    """Grade the targeter's claim choices against the labeled cases."""
    if not cases:
        raise ValueError("no merge cases to evaluate")
    graded: list[MergeEvalCase] = []
    correct = 0
    for case in cases:
        claims = [make_claim(statement, "seed", _SEED_TIME) for statement in case.existing]
        chosen = targeter.target(case.update, claims)
        predicted = _index_of(claims, chosen)
        ok = predicted == case.target
        correct += int(ok)
        graded.append(MergeEvalCase(case.band, case.target, predicted, ok))
    return MergeEvalReport(case_count=len(cases), correct=correct, cases=tuple(graded))


def _index_of(claims: list[Claim], claim_id: str | None) -> int:
    if claim_id is None:
        return NOVEL
    for index, claim in enumerate(claims):
        if claim.claim_id == claim_id:
            return index
    return NOVEL


def _require_str(record: dict[str, object], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str):
        raise ValueError(f"missing or non-string field {key!r}")
    return value


def _require_int(record: dict[str, object], key: str) -> int:
    value = record.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"missing or non-integer field {key!r}")
    return value


def _require_str_list(record: dict[str, object], key: str) -> list[str]:
    value = record.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"missing or non-string-list field {key!r}")
    return [item for item in value if isinstance(item, str)]
