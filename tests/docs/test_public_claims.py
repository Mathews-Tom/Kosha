"""M1 public claim-boundary guardrails.

Kosha's real-model Gate-0 runs returned NO-GO (`docs/gate0-status.md`) and
M14+ product expansion is halted until a future pre-registered run records a
GO. The public docs are only allowed to describe this honestly: the
governance guarantee (no silent overwrites, replayable lineage) is real,
decision-quality superiority over a good prompt is not, and the MCP
traversal boundary does not sandbox a host agent that also carries generic
filesystem tools -- today.

This module scans every public-facing surface for two kinds of regressions:

* a required disclosure silently disappearing (the NO-GO verdict, the M14+
  halt, or the "not sandboxed ... today" filesystem boundary), and
* a banned claim reappearing without the negation/qualifier that makes it
  honest (e.g. "the loop beats a good prompt" with no "does not" in sight,
  or "a host agent cannot grep the bundle" with no sandboxed/future
  qualifier in sight).

Detection is line-based: every prose paragraph and every markdown table row
in these docs is written on a single source line (verified against the
current corpus), so a match's own line is the right-sized window to look
for a nearby allow-cue before flagging it -- wide enough to catch "does not
beat" a few words away, narrow enough that an unrelated negation elsewhere
in the file can't excuse a real regression.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

DOC_PATHS: tuple[Path, ...] = (
    REPO_ROOT / "README.md",
    REPO_ROOT / "ACCEPTANCE_REPORT.md",
    REPO_ROOT / "PREMISE_REPORT.md",
    *sorted((REPO_ROOT / "docs").glob("*.md")),
    REPO_ROOT / "consumer" / "AGENTS.fragment.md",
    REPO_ROOT / "consumer" / "kosha-traversal" / "SKILL.md",
)
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
ALL_SCANNED_PATHS: tuple[Path, ...] = (*DOC_PATHS, PYPROJECT_PATH)


def _relname(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def _normalize(line: str) -> str:
    """Strip markdown emphasis/code markers and collapse whitespace.

    "does **not** beat" must read as "does not beat", or a bolded negation
    word would silently break a multi-word allow-cue substring match.
    """
    return re.sub(r"\s+", " ", re.sub(r"[*_`]", "", line)).strip()


def _normalized_lines(path: Path) -> list[str]:
    return [_normalize(line) for line in path.read_text(encoding="utf-8").splitlines()]


# ---------------------------------------------------------------------------
# Banned-claim rules: a hit requires the pattern to match AND none of the
# rule's allow-cues to be present on that same (normalized) line.
# ---------------------------------------------------------------------------

_BEAT = (
    r"(?<![\w-])(?:beats?|beating|outperforms?|outperforming"
    r"|wins?\s+over|winning\s+over|better\s+than)(?![\w-])"
)
_PROMPT = r"(?<![\w-])(?:prompts?(?:-only|-based)?|prompting)(?![\w-])"
_CANNOT = (
    r"(?<![\w-])(?:cannot|can't|is unable to|are unable to|is not able to"
    r"|structurally cannot|structurally can't)(?![\w-])"
)
_SEARCHLIKE = r"(?<![\w-])(?:grep(?:s|ping)?|search(?:es|ing)?)(?![\w-])"

BANNED_RULES: dict[str, tuple[re.Pattern[str], tuple[str, ...]]] = {
    # "the loop beats a good prompt" / "wins over prompt-only baselines" —
    # a real-model win over a prompt-only baseline, unqualified.
    "prompt_superiority": (
        re.compile(rf"{_BEAT}[^.\n?!]{{0,120}}{_PROMPT}", re.IGNORECASE),
        (
            "does not currently beat",
            "does not beat",
            "did not beat",
            "no longer beats",
            "cannot currently beat",
            "test whether",
            "tests whether",
            "trailing prompt",
            "trailed prompt",
            "found the opposite",
        ),
    ),
    # "Kosha delivers decision-quality superiority" — an unqualified
    # decision-quality superiority claim.
    "decision_quality_superiority": (
        re.compile(r"(?<![\w-])superior(?:ity)?(?![\w-])", re.IGNORECASE),
        (
            "does not currently claim",
            "does not claim",
            "not authorize",
            "does not authorize",
            "found the opposite",
        ),
    ),
    # "a host agent cannot grep the bundle" — a structural capability claim
    # about the shipped surface, banned unless it names the sandboxed/
    # future/instruction-only boundary that would actually make it true.
    "host_agent_cannot_grep": (
        re.compile(
            rf"{_CANNOT}[^.\n?!]{{0,100}}{_SEARCHLIKE}|{_SEARCHLIKE}[^.\n?!]{{0,100}}{_CANNOT}",
            re.IGNORECASE,
        ),
        (
            "does not currently claim",
            "does not claim",
            "future",
            "not sandboxed",
            "instruction-only",
            "instruction only",
        ),
    ),
}


def find_banned_claims(text: str) -> list[tuple[str, int, str]]:
    """Return (rule, 1-based line number, normalized line) for every line
    that trips a banned-claim rule without a nearby allow-cue."""
    violations: list[tuple[str, int, str]] = []
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = _normalize(raw_line)
        lowered = line.lower()
        for rule, (pattern, allow_cues) in BANNED_RULES.items():
            if pattern.search(line) and not any(cue in lowered for cue in allow_cues):
                violations.append((rule, line_no, line))
    return violations


# ---------------------------------------------------------------------------
# Required-disclosure rules: at least one (normalized) line across the whole
# scanned corpus must match.
# ---------------------------------------------------------------------------

REQUIRED_DISCLOSURES: dict[str, re.Pattern[str]] = {
    "real_model_no_go": re.compile(
        r"real-model[^\n]{0,150}\bno-go\b|\bno-go\b[^\n]{0,150}real-model",
        re.IGNORECASE,
    ),
    "m14_plus_halted": re.compile(
        r"m14\+[^\n]{0,80}\bhalt|halt[^\n]{0,80}m14\+",
        re.IGNORECASE,
    ),
    "filesystem_not_sandboxed_today": re.compile(
        r"(?:host (?:agent|session)|generic filesystem tools)[^\n]{0,160}"
        r"not sandboxed[^\n]{0,60}(?:today|currently)",
        re.IGNORECASE,
    ),
}


def _disclosure_present(pattern: re.Pattern[str]) -> bool:
    return any(
        pattern.search(line)
        for path in ALL_SCANNED_PATHS
        if path.is_file()
        for line in _normalized_lines(path)
    )


# ---------------------------------------------------------------------------
# Corpus scans
# ---------------------------------------------------------------------------


def test_all_expected_public_surfaces_exist() -> None:
    # Guards against a silently broken glob/path list passing everything else
    # vacuously — if this list shrinks, so does the coverage below.
    missing = [_relname(p) for p in ALL_SCANNED_PATHS if not p.is_file()]
    assert not missing, f"expected public surface(s) missing: {missing}"
    assert len(DOC_PATHS) >= 10


@pytest.mark.parametrize("path", DOC_PATHS, ids=_relname)
def test_public_doc_has_no_banned_m1_claims(path: Path) -> None:
    violations = find_banned_claims(path.read_text(encoding="utf-8"))
    assert not violations, (
        f"{_relname(path)} reintroduces a banned M1 claim: "
        + "; ".join(f"{rule} (line {n}): {snippet}" for rule, n, snippet in violations)
    )


def test_pyproject_metadata_has_no_banned_m1_claims() -> None:
    violations = find_banned_claims(PYPROJECT_PATH.read_text(encoding="utf-8"))
    assert not violations, (
        "pyproject.toml reintroduces a banned M1 claim: "
        + "; ".join(f"{rule} (line {n}): {snippet}" for rule, n, snippet in violations)
    )


@pytest.mark.parametrize("name", sorted(REQUIRED_DISCLOSURES))
def test_public_docs_carry_required_m1_disclosure(name: str) -> None:
    assert _disclosure_present(REQUIRED_DISCLOSURES[name]), (
        f"no public doc/metadata surface discloses the required M1 boundary {name!r}; "
        "the real-model NO-GO verdict, the M14+ halt, and the "
        "generic-filesystem-tools-not-sandboxed-today boundary must all stay visible"
    )


# ---------------------------------------------------------------------------
# Scanner unit tests: prove the rules above actually have teeth, independent
# of whatever the current docs happen to say.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "banned_sentence",
    [
        "The Kosha loop now beats a good prompt on decision quality.",
        "Real-model results show Kosha wins over prompt-only baselines.",
        "The maintenance loop is better than a prompt at every benchmark.",
        "Kosha now delivers decision-quality superiority in every benchmark.",
        "A host agent cannot grep the bundle to find what it needs.",
        "A host agent structurally cannot grep the corpus for answers.",
    ],
    ids=[
        "beats-a-good-prompt",
        "wins-over-prompt-only",
        "better-than-a-prompt",
        "decision-quality-superiority",
        "host-agent-cannot-grep",
        "host-agent-structurally-cannot-grep",
    ],
)
def test_scanner_flags_reintroduced_banned_claims(banned_sentence: str) -> None:
    assert find_banned_claims(banned_sentence), (
        f"expected a banned-claim hit for: {banned_sentence!r}"
    )


@pytest.mark.parametrize(
    "allowed_sentence",
    [
        "The loop does not currently beat a good prompt on decision quality.",
        "The real-model Gate-0 runs test whether the loop beats a prompt-only baseline.",
        "Kosha does not claim decision-quality superiority over a good prompt.",
        "This report does not authorize decision-quality superiority or M14+ expansion.",
        "Kosha does not claim that a host agent cannot grep the bundle today.",
        "A host agent cannot grep the bundle, but a future sandboxed boundary could enforce that.",
        "The file-based fallback is instruction-only: "
        "a host agent cannot grep the bundle by contract alone.",
        "Define the must-beat-a-prompt bar before reopening the product-quality claim.",
    ],
    ids=[
        "does-not-currently-beat",
        "test-whether-it-beats",
        "does-not-claim-superiority",
        "does-not-authorize-superiority",
        "does-not-claim-cannot-grep",
        "cannot-grep-future-sandboxed",
        "cannot-grep-instruction-only",
        "must-beat-a-prompt-bar-is-not-a-claim",
    ],
)
def test_scanner_allows_negated_or_qualified_claims(allowed_sentence: str) -> None:
    assert find_banned_claims(allowed_sentence) == []


def test_no_go_and_halt_disclosure_patterns_match_canonical_phrasing() -> None:
    sample = _normalize(
        "**Real-model Gate-0 verdict** — three real-model runs returned **NO-GO**. "
        "M14+ product expansion remains halted."
    )
    assert REQUIRED_DISCLOSURES["real_model_no_go"].search(sample)
    assert REQUIRED_DISCLOSURES["m14_plus_halted"].search(sample)


def test_filesystem_boundary_disclosure_pattern_matches_canonical_phrasing() -> None:
    sample = _normalize(
        "a host agent with generic filesystem tools is not sandboxed by Kosha today."
    )
    assert REQUIRED_DISCLOSURES["filesystem_not_sandboxed_today"].search(sample)


def test_required_disclosure_patterns_do_not_match_when_silently_dropped() -> None:
    # If a future edit quietly deleted every disclosure, the aggregate check
    # must actually be capable of catching it -- prove the patterns are not
    # vacuously true.
    sample = _normalize("Kosha ships a governance skill with a replayable audit trail.")
    for pattern in REQUIRED_DISCLOSURES.values():
        assert pattern.search(sample) is None
