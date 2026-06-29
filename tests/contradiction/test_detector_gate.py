"""The detector-gated judge: code-owned detection forcing reconcile (spike S2)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from kosha.contradiction import (
    DetectorGatedJudge,
    assert_no_silent_overwrite,
    reconcile,
)
from kosha.contradiction.detect import (
    ContradictionVerdict,
    DiffSignal,
    Judgment,
    structured_diff,
)
from kosha.merge import make_claim

_START = datetime(2026, 1, 1, tzinfo=UTC)


class _SilentJudge:
    """An LLM judge that misses every conflict; counts how often it is consulted."""

    def __init__(self) -> None:
        self.calls = 0

    @property
    def name(self) -> str:
        return "silent"

    def judge(self, old: str, new: str, signal: DiffSignal) -> Judgment:
        self.calls += 1
        return Judgment(ContradictionVerdict.NONE, "silent: no conflict")


def _verdict(gated: DetectorGatedJudge, old: str, new: str) -> ContradictionVerdict:
    return gated.judge(old, new, structured_diff(old, new)).verdict


def test_detector_forces_numeric_conflict_the_llm_missed() -> None:
    llm = _SilentJudge()
    gated = DetectorGatedJudge(llm)
    old = "The cache holds 8 entries before eviction."
    new = "The cache holds 64 entries before eviction."
    assert _verdict(gated, old, new) is ContradictionVerdict.CONFLICT
    assert llm.calls == 0  # the deterministic detector settled it without the LLM


def test_detector_forces_negation_conflict_the_llm_missed() -> None:
    llm = _SilentJudge()
    gated = DetectorGatedJudge(llm)
    old = "The endpoint raises an error on an empty body."
    new = "The endpoint does not raise an error on an empty body."
    assert _verdict(gated, old, new) is ContradictionVerdict.CONFLICT
    assert llm.calls == 0


def test_ambiguous_residue_defers_to_the_llm() -> None:
    llm = _SilentJudge()
    gated = DetectorGatedJudge(llm)
    # Shared subject, no numeric/negation cue: the detector cannot decide, so the
    # LLM is consulted (and here it misses -> NONE). This is the fair contrast.
    old = "copytree copies the directory tree preserving metadata."
    new = "copytree moves the directory tree discarding metadata."
    assert _verdict(gated, old, new) is ContradictionVerdict.NONE
    assert llm.calls == 1


def test_unrelated_pair_settled_without_the_llm() -> None:
    llm = _SilentJudge()
    gated = DetectorGatedJudge(llm)
    assert _verdict(gated, "Alpha concerns billing.", "Zulu concerns telemetry.") is (
        ContradictionVerdict.NONE
    )
    assert llm.calls == 0  # clearly unrelated -> no LLM call


def test_gated_reconcile_retains_prior_on_a_conflict_the_llm_missed() -> None:
    gated = DetectorGatedJudge(_SilentJudge())
    prior = "The cache holds 8 entries before eviction."
    old = make_claim(prior, "corpus", _START, effective_from=_START)
    new = make_claim(
        "The cache holds 64 entries before eviction.",
        "update",
        datetime(2027, 1, 1, tzinfo=UTC),
        effective_from=datetime(2027, 1, 1, tzinfo=UTC),
    )
    result = reconcile([old], new, authority={"corpus": 1, "update": 1}, judge=gated)
    assert result.conflicting  # detector forced reconcile despite the LLM miss
    assert any(claim.statement == prior for claim in result.claims)
    assert_no_silent_overwrite([old], result.claims)  # must not raise


def test_bare_llm_reconcile_misses_the_same_conflict() -> None:
    # The fair contrast: the LLM-only judge misses the numeric conflict, so the
    # loop's edge is entirely the code-owned detector gate above.
    prior = "The cache holds 8 entries before eviction."
    old = make_claim(prior, "corpus", _START, effective_from=_START)
    new = make_claim(
        "The cache holds 64 entries before eviction.",
        "update",
        datetime(2027, 1, 1, tzinfo=UTC),
        effective_from=datetime(2027, 1, 1, tzinfo=UTC),
    )
    result = reconcile([old], new, authority={"corpus": 1, "update": 1}, judge=_SilentJudge())
    assert not result.conflicting


def test_overlap_min_is_validated() -> None:
    with pytest.raises(ValueError, match="overlap_min"):
        DetectorGatedJudge(_SilentJudge(), overlap_min=1.5)
