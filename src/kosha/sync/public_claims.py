"""Public claim-boundary scanner reused by tests and ``kosha sync check``.

Kosha's real-model Gate-0 runs returned NO-GO and M14+ product expansion is
halted until a future pre-registered run records a GO. Public surfaces may
describe the governance guarantee (no silent overwrites, replayable lineage) as
real, but must not claim decision-quality superiority over a good prompt or
imply that the MCP/fallback traversal boundary sandboxes a host agent that also
has generic filesystem tools today.

Detection is line-based: public prose paragraphs and markdown table rows in the
current corpus are authored on single lines, so a match's own line is the right
window for allow-cues. It is wide enough to catch "does not beat" a few words
away and narrow enough that an unrelated negation elsewhere in the file cannot
excuse a real regression.
"""

from __future__ import annotations

import re
from pathlib import Path
from re import Pattern

from kosha.sync.check import SyncMismatch

PUBLIC_DOC_RELATIVE_PATHS: tuple[Path, ...] = (
    Path("README.md"),
    Path("ACCEPTANCE_REPORT.md"),
    Path("PREMISE_REPORT.md"),
    Path("consumer/AGENTS.fragment.md"),
    Path("consumer/kosha-traversal/SKILL.md"),
)
DOCS_GLOB = "*.md"
PYPROJECT_RELATIVE_PATH = Path("pyproject.toml")

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

# Banned-claim rules: a hit requires the pattern to match and none of the
# rule's allow-cues to be present on that same normalized line.
BANNED_RULES: dict[str, tuple[Pattern[str], tuple[str, ...]]] = {
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
    # "Kosha beats RAG" — an unqualified real-world RAG superiority claim.
    "real_rag_superiority": (
        re.compile(
            rf"{_BEAT}[^.\n?!]{{0,120}}\brag\b|\brag\b[^.\n?!]{{0,120}}{_BEAT}",
            re.IGNORECASE,
        ),
        (
            "does not currently claim",
            "does not claim",
            "toy providers",
            "toy provider",
            "deterministic",
            "benchmark-only",
            "test whether",
            "tests whether",
            "at what",
        ),
    ),
    # "a host agent cannot grep the bundle" — a structural capability claim
    # about the shipped surface, banned unless it names the sandboxed/
    # future/instruction-only boundary that would actually make it true.
    "host_agent_cannot_grep": (
        re.compile(
            rf"{_CANNOT}[^.\n?!]{{0,100}}{_SEARCHLIKE}|"
            rf"{_SEARCHLIKE}[^.\n?!]{{0,100}}{_CANNOT}",
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

REQUIRED_DISCLOSURES: dict[str, Pattern[str]] = {
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

def public_doc_paths(repo_root: Path) -> tuple[Path, ...]:
    """Return public prose surfaces scanned for claim-boundary regressions."""

    docs = tuple(sorted((repo_root / "docs").glob(DOCS_GLOB)))
    explicit = tuple(repo_root / relative for relative in PUBLIC_DOC_RELATIVE_PATHS)
    return (*explicit, *docs)


def scanned_paths(repo_root: Path) -> tuple[Path, ...]:
    """Return every public claim surface, including package metadata."""

    return (*public_doc_paths(repo_root), repo_root / PYPROJECT_RELATIVE_PATH)


def find_banned_claims(text: str) -> list[tuple[str, int, str]]:
    """Return claim-boundary violations as ``(rule, line, normalized line)``."""

    violations: list[tuple[str, int, str]] = []
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = normalize_claim_line(raw_line)
        lowered = line.lower()
        for rule, (pattern, allow_cues) in BANNED_RULES.items():
            if pattern.search(line) and not any(cue in lowered for cue in allow_cues):
                violations.append((rule, line_no, line))
    return violations


def disclosure_present(paths: tuple[Path, ...], pattern: Pattern[str]) -> bool:
    """Return whether any scanned path contains a required disclosure."""

    return any(
        pattern.search(line)
        for path in paths
        if path.is_file()
        for line in normalized_lines(path)
    )


def normalized_lines(path: Path) -> list[str]:
    """Return normalized lines from ``path`` for claim scanning."""

    return [normalize_claim_line(line) for line in path.read_text(encoding="utf-8").splitlines()]


def normalize_claim_line(line: str) -> str:
    """Strip markdown emphasis/code markers and collapse whitespace."""

    return re.sub(r"\s+", " ", re.sub(r"[*_`]", "", line)).strip()


def check_public_claims(repo_root: Path) -> tuple[SyncMismatch, ...]:
    """Return sync mismatches for public claim-boundary guardrail failures."""

    all_paths = scanned_paths(repo_root)
    missing = tuple(path for path in all_paths if not path.is_file())
    if missing:
        return tuple(
            SyncMismatch(
                surface="public-claims",
                path=path,
                message="expected public claim surface is missing",
            )
            for path in missing
        )

    mismatches: list[SyncMismatch] = []
    for path in all_paths:
        violations = find_banned_claims(path.read_text(encoding="utf-8"))
        if violations:
            mismatches.append(
                SyncMismatch(
                    surface="public-claims",
                    path=path,
                    message="public surface reintroduces a banned M1 claim",
                    details=tuple(
                        f"{rule} (line {line_no}): {snippet}"
                        for rule, line_no, snippet in violations
                    ),
                )
            )
    disclosure_details = tuple(
        f"missing required disclosure: {name}"
        for name, pattern in sorted(REQUIRED_DISCLOSURES.items())
        if not disclosure_present(all_paths, pattern)
    )
    if disclosure_details:
        mismatches.append(
            SyncMismatch(
                surface="public-claims",
                path=repo_root,
                message="public surfaces dropped required M1 claim-boundary disclosures",
                details=disclosure_details,
            )
        )
    return tuple(mismatches)
