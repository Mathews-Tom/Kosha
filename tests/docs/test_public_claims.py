"""M1 public claim-boundary guardrails."""

from __future__ import annotations

from pathlib import Path

import pytest

from kosha.sync.public_claims import (
    PYPROJECT_RELATIVE_PATH,
    REQUIRED_DISCLOSURES,
    check_public_claims,
    disclosure_present,
    find_banned_claims,
    normalize_claim_line,
    public_doc_paths,
    scanned_paths,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DOC_PATHS = public_doc_paths(REPO_ROOT)
PYPROJECT_PATH = REPO_ROOT / PYPROJECT_RELATIVE_PATH
ALL_SCANNED_PATHS = scanned_paths(REPO_ROOT)


def _relname(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


# ---------------------------------------------------------------------------
# Corpus scans
# ---------------------------------------------------------------------------


def test_all_expected_public_surfaces_exist() -> None:
    # Guards against a silently broken path list passing everything else vacuously.
    missing = [_relname(path) for path in ALL_SCANNED_PATHS if not path.is_file()]
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
    assert disclosure_present(ALL_SCANNED_PATHS, REQUIRED_DISCLOSURES[name]), (
        f"no public doc/metadata surface discloses the required M1 boundary {name!r}; "
        "the real-model NO-GO verdict, the M14+ halt, and the "
        "generic-filesystem-tools-not-sandboxed-today boundary must all stay visible"
    )


def test_sync_public_claim_checker_is_clean_for_current_repo() -> None:
    assert check_public_claims(REPO_ROOT) == ()


# ---------------------------------------------------------------------------
# check_public_claims: repo-level wiring exercised against synthetic temp
# repos so a regression is caught without mutating the checked-in docs.
# ---------------------------------------------------------------------------


_CANONICAL_DISCLOSURES = (
    "**Real-model Gate-0 verdict** — three real-model runs returned **NO-GO**. "
    "M14+ product expansion remains halted.\n\n"
    "A host agent with generic filesystem tools is not sandboxed by Kosha today.\n"
)


def _minimal_scanned_repo_files(readme_body: str) -> dict[Path, str]:
    """Every path ``scanned_paths`` requires to exist, with placeholder prose."""
    return {
        Path("README.md"): readme_body,
        Path("ACCEPTANCE_REPORT.md"): "# Acceptance Report\n\nNothing notable here.\n",
        Path("PREMISE_REPORT.md"): "# Premise Report\n\nNothing notable here.\n",
        Path("consumer/AGENTS.fragment.md"): "# Agents Fragment\n\nNothing notable here.\n",
        Path("consumer/kosha-traversal/SKILL.md"): (
            "# Kosha Traversal Skill\n\nNothing notable here.\n"
        ),
        Path("pyproject.toml"): '[project]\nname = "kosha"\n',
    }


def _write_repo(root: Path, files: dict[Path, str]) -> None:
    for relative, content in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def test_check_public_claims_flags_a_drifted_doc_and_names_the_banned_rule(
    tmp_path: Path,
) -> None:
    files = _minimal_scanned_repo_files(f"# Kosha\n\n{_CANONICAL_DISCLOSURES}")
    files[Path("PREMISE_REPORT.md")] = (
        "# Premise Report\n\nThe Kosha loop now beats a good prompt on decision quality.\n"
    )
    _write_repo(tmp_path, files)

    mismatches = check_public_claims(tmp_path)

    assert len(mismatches) == 1
    mismatch = mismatches[0]
    assert mismatch.surface == "public-claims"
    assert mismatch.path == tmp_path / "PREMISE_REPORT.md"
    assert any("prompt_superiority" in detail for detail in mismatch.details)


def test_check_public_claims_flags_missing_required_disclosures(tmp_path: Path) -> None:
    files = _minimal_scanned_repo_files("# Kosha\n\nNothing to disclose here.\n")
    _write_repo(tmp_path, files)

    mismatches = check_public_claims(tmp_path)

    assert len(mismatches) == 1
    mismatch = mismatches[0]
    assert mismatch.surface == "public-claims"
    assert any("missing required disclosure" in detail for detail in mismatch.details)


def test_check_public_claims_flags_a_missing_file_at_its_own_path(
    tmp_path: Path,
) -> None:
    files = _minimal_scanned_repo_files(f"# Kosha\n\n{_CANONICAL_DISCLOSURES}")
    del files[Path("PREMISE_REPORT.md")]
    _write_repo(tmp_path, files)

    mismatches = check_public_claims(tmp_path)

    assert len(mismatches) == 1
    mismatch = mismatches[0]
    assert mismatch.surface == "public-claims"
    assert mismatch.path == tmp_path / "PREMISE_REPORT.md"
    assert mismatch.path != tmp_path
    assert mismatch.message == "expected public claim surface is missing"


# ---------------------------------------------------------------------------
# Scanner unit tests: prove the rules have teeth independently of current docs.
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
        "Kosha beats RAG on both tokens and wall-clock latency.",
        "The index-traversal approach is superior to RAG.",
    ],
    ids=[
        "beats-a-good-prompt",
        "wins-over-prompt-only",
        "better-than-a-prompt",
        "decision-quality-superiority",
        "host-agent-cannot-grep",
        "host-agent-structurally-cannot-grep",
        "beats-rag",
        "superior-to-rag",
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
        "Kosha does not currently claim retrieval superiority over real-world RAG systems.",
        "These figures verify deterministic mechanics, not a win over real RAG.",
        "At what corpus size and price does index-traversal actually beat RAG?",
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
        "does-not-claim-rag-superiority",
        "deterministic-rag-caveat",
        "question-about-beating-rag",
    ],
)
def test_scanner_allows_negated_or_qualified_claims(allowed_sentence: str) -> None:
    assert find_banned_claims(allowed_sentence) == []


def test_no_go_and_halt_disclosure_patterns_match_canonical_phrasing() -> None:
    sample = normalize_claim_line(
        "**Real-model Gate-0 verdict** — three real-model runs returned **NO-GO**. "
        "M14+ product expansion remains halted."
    )
    assert REQUIRED_DISCLOSURES["real_model_no_go"].search(sample)
    assert REQUIRED_DISCLOSURES["m14_plus_halted"].search(sample)


def test_filesystem_boundary_disclosure_pattern_matches_canonical_phrasing() -> None:
    sample = normalize_claim_line(
        "a host agent with generic filesystem tools is not sandboxed by Kosha today."
    )
    assert REQUIRED_DISCLOSURES["filesystem_not_sandboxed_today"].search(sample)


def test_required_disclosure_patterns_do_not_match_when_silently_dropped() -> None:
    sample = normalize_claim_line("Kosha ships a governance skill with a replayable audit trail.")
    for pattern in REQUIRED_DISCLOSURES.values():
        assert pattern.search(sample) is None
