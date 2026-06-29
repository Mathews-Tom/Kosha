"""The regime-spanning, scaled held-out contradiction set (spike S2).

M13 measured contradiction safety on six clean, single-claim cases — exactly the
shape a good prompt handles. Gate-0 v2 measures it on >=100 held-out
contradictions that span the conflict *regimes* a buyer's corpus actually
contains and the at-scale *contexts* where a prompt's best-effort breaks:

* regimes (the conflict shape): ``numeric`` (differing value), ``negation``
  (polarity flip), ``unit`` (same number, different unit), ``partial`` (one
  clause of several flips), ``temporal`` (a later release reverses an earlier
  default), ``adversarial`` (a paraphrase with no numeric/negation cue);
* scales (where the prior sits): ``clean`` (a single prior claim),
  ``buried_body`` (the prior is one clause in a long body), ``deep_history``
  (the prior is one claim among a deep in-force history).

The set is generated deterministically from real stdlib subjects so it is
byte-reproducible and grounded in the external corpus, then committed as
``evals/realworld/contradictions_v2.jsonl``. **It is strictly held out: it is
measure-only and never used to calibrate any threshold (those fit on the seed
labels alone).** ``build_contradiction_set`` is its provenance.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from kosha.bench.gate2.criterion import REGIMES

# Where the conflicting prior sits relative to the rest of the concept.
SCALES: tuple[str, ...] = ("clean", "buried_body", "deep_history")

# Real stdlib subjects so each contradiction is grounded in the external corpus.
_SUBJECTS: tuple[str, ...] = (
    "json.dumps", "json.loads", "tempfile.TemporaryDirectory", "shutil.copytree",
    "functools.lru_cache", "re.findall", "base64.b64encode", "copy.deepcopy",
    "collections.Counter", "itertools.groupby", "textwrap.dedent", "heapq.heappush",
    "bisect.insort", "gzip.open", "hashlib.sha256", "random.shuffle",
    "statistics.median", "struct.pack", "datetime.fromisoformat", "zipfile.ZipFile",
)
# Cases generated per regime; 6 regimes x 18 = 108 >= the pre-registered 100.
_PER_REGIME = 18


@dataclass(frozen=True)
class ContradictionCase:
    """One held-out contradiction: a prior claim and a statement that conflicts."""

    id: str
    regime: str
    scale: str
    subject: str
    prior: str
    new: str
    depth: int
    filler: int


def build_contradiction_set() -> tuple[ContradictionCase, ...]:
    """Generate the full held-out set deterministically (spans regimes x scales)."""
    cases: list[ContradictionCase] = []
    for regime in REGIMES:
        for offset in range(_PER_REGIME):
            subject = _SUBJECTS[offset % len(_SUBJECTS)]
            scale = SCALES[offset % len(SCALES)]
            prior, new = _statements(regime, subject, offset)
            cases.append(
                ContradictionCase(
                    id=f"{regime}-{offset:02d}",
                    regime=regime,
                    scale=scale,
                    subject=subject,
                    prior=prior,
                    new=new,
                    depth=(10 + offset % 11) if scale == "deep_history" else 0,
                    filler=(8 + offset % 9) if scale == "buried_body" else 0,
                )
            )
    return tuple(cases)


def _statements(regime: str, subject: str, offset: int) -> tuple[str, str]:
    if regime == "numeric":
        low, high = 8 + offset, 16 + 2 * offset
        return (
            f"{subject} returns at most {low} results per call.",
            f"{subject} returns at most {high} results per call.",
        )
    if regime == "negation":
        return (
            f"{subject} raises an error when the input is empty.",
            f"{subject} does not raise an error when the input is empty.",
        )
    if regime == "unit":
        amount = 5 + offset % 7
        return (
            f"{subject} times out after {amount} seconds.",
            f"{subject} times out after {amount} minutes.",
        )
    if regime == "partial":
        return (
            f"{subject} processes items in ascending order and is stable.",
            f"{subject} processes items in descending order.",
        )
    if regime == "temporal":
        v1, v2 = 1 + offset % 3, 4 + offset % 3
        return (
            f"As of release {v1}, {subject} defaults to UTF-8 encoding.",
            f"As of release {v2}, {subject} defaults to ASCII encoding.",
        )
    if regime == "adversarial":
        return (
            f"{subject} copies the resource, preserving its original metadata.",
            f"{subject} relocates the resource and discards its original metadata.",
        )
    raise ValueError(f"unknown regime {regime!r}")


def render_jsonl(cases: Sequence[ContradictionCase]) -> str:
    """Render cases as one JSON object per line (the committed file format)."""
    lines = [
        json.dumps(
            {
                "id": case.id,
                "regime": case.regime,
                "scale": case.scale,
                "subject": case.subject,
                "prior": case.prior,
                "new": case.new,
                "depth": case.depth,
                "filler": case.filler,
            }
        )
        for case in cases
    ]
    return "\n".join(lines) + "\n"


def write_contradictions(path: Path) -> int:
    """Write the generated held-out set to ``path``; return the case count."""
    cases = build_contradiction_set()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_jsonl(cases), encoding="utf-8")
    return len(cases)


def load_contradictions(path: Path) -> tuple[ContradictionCase, ...]:
    """Load the held-out contradiction set from a JSONL file (fail-loud)."""
    cases: list[ContradictionCase] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        record = json.loads(stripped)
        if not isinstance(record, dict):
            raise ValueError(f"{path}:{number} is not a JSON object")
        cases.append(
            ContradictionCase(
                id=_req_str(record, "id", path, number),
                regime=_req_str(record, "regime", path, number),
                scale=_req_str(record, "scale", path, number),
                subject=_req_str(record, "subject", path, number),
                prior=_req_str(record, "prior", path, number),
                new=_req_str(record, "new", path, number),
                depth=_req_int(record, "depth", path, number),
                filler=_req_int(record, "filler", path, number),
            )
        )
    if not cases:
        raise ValueError(f"{path} held no contradiction cases")
    return tuple(cases)


def regimes_present(cases: Sequence[ContradictionCase]) -> tuple[str, ...]:
    """Distinct regimes the set covers, in the pre-registered order."""
    present = {case.regime for case in cases}
    return tuple(regime for regime in REGIMES if regime in present)


def _req_str(record: dict[str, object], key: str, path: Path, number: int) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{path}:{number} field {key!r} must be a non-empty string")
    return value


def _req_int(record: dict[str, object], key: str, path: Path, number: int) -> int:
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{path}:{number} field {key!r} must be an integer")
    return value
