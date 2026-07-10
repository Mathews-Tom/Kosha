"""Gate-0 v2 re-run smoke fixtures (M3, DEVELOPMENT_PLAN §4 M3 verification).

Two commands are pre-registered as verification: an offline smoke —
``kosha bench realworld --ingests 5 --max-queries 6`` — that must stay
deterministic under the local providers, and a full-scale run — ``--ingests
50`` — that is only a valid recorded Gate-0 verdict with real providers
configured. This module locks in both contracts against the exact CLI
entrypoint, not just the underlying runner function.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kosha.cli import main

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "bundles" / "pydoc-stdlib"
S2V3_CORPUS = ROOT / "bundles" / "paper-s2v3-corpus"
S2V3_QUERIES = ROOT / "evals" / "paper_s2v3" / "queries.jsonl"
S2V3_MAINTENANCE = ROOT / "evals" / "paper_s2v3" / "maintenance.jsonl"


def _run_cli(
    report_path: Path,
    *,
    ingests: int,
    max_queries: int,
    corpus: Path = CORPUS,
    queries: Path | None = None,
    maintenance: Path | None = None,
    fidelity_targeter: str | None = None,
) -> int:
    args = [
        "bench",
        "realworld",
        "--corpus",
        str(corpus),
        "--ingests",
        str(ingests),
        "--max-queries",
        str(max_queries),
        "--seed-concepts",
        "12",
        "--report",
        str(report_path),
    ]
    if queries:
        args.extend(["--queries", str(queries)])
    if maintenance:
        args.extend(["--maintenance", str(maintenance)])
    if fidelity_targeter:
        args.extend(["--fidelity-targeter", fidelity_targeter])
    return main(args)


def test_offline_smoke_exits_zero_and_records_a_verdict(tmp_path: Path) -> None:
    report_path = tmp_path / "ACCEPTANCE_REPORT.md"
    code = _run_cli(report_path, ingests=5, max_queries=6)
    assert code == 0
    text = report_path.read_text(encoding="utf-8")
    assert "**Verdict: GO**" in text or "**Verdict: NO-GO**" in text


def test_offline_smoke_is_deterministic(tmp_path: Path) -> None:
    # Local lexical/extractive providers are deterministic, so re-running the
    # exact pre-registered smoke command must reproduce the same report.
    first = tmp_path / "first.md"
    second = tmp_path / "second.md"
    assert _run_cli(first, ingests=5, max_queries=6) == 0
    assert _run_cli(second, ingests=5, max_queries=6) == 0
    assert first.read_text(encoding="utf-8") == second.read_text(encoding="utf-8")


def test_offline_smoke_does_not_warn_about_local_providers(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Below the real Gate-0 ingest threshold, local providers are expected and
    # must not be flagged as an invalid Gate-0 attempt.
    assert _run_cli(tmp_path / "report.md", ingests=5, max_queries=6) == 0
    assert "NOT a valid Gate-0 verdict" not in capsys.readouterr().err


def test_full_scale_run_without_real_providers_warns_instead_of_a_silent_verdict(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # DEVELOPMENT_PLAN M3 gap: "a GO/NO-GO verdict is only valid when real
    # providers are configured." A full-scale (>=MIN_INGESTS) attempt with the
    # default local providers must exit 0 (it is still a runnable smoke) but
    # loudly say the result is not a valid recorded Gate-0 verdict.
    code = _run_cli(tmp_path / "report.md", ingests=50, max_queries=2)
    assert code == 0
    assert "NOT a valid Gate-0 verdict" in capsys.readouterr().err


def test_s2v3_offline_smoke_exits_zero_and_records_a_verdict(tmp_path: Path) -> None:
    if not S2V3_CORPUS.exists():
        pytest.skip("s2v3 corpus not ready")
    report_path = tmp_path / "S2V3_REPORT.md"
    code = _run_cli(
        report_path,
        ingests=5,
        max_queries=6,
        corpus=S2V3_CORPUS,
        queries=S2V3_QUERIES,
        maintenance=S2V3_MAINTENANCE,
    )
    assert code == 0
    text = report_path.read_text(encoding="utf-8")
    assert "**Verdict: GO**" in text or "**Verdict: NO-GO**" in text


def test_s2v3_offline_smoke_is_deterministic(tmp_path: Path) -> None:
    if not S2V3_CORPUS.exists():
        pytest.skip("s2v3 corpus not ready")
    # Same determinism contract as the default-corpus smoke (M2 PR-4): local
    # providers must reproduce a byte-identical report on the second-corpus
    # path too, not just the default pydoc-stdlib path.
    common = {
        "ingests": 5,
        "max_queries": 6,
        "corpus": S2V3_CORPUS,
        "queries": S2V3_QUERIES,
        "maintenance": S2V3_MAINTENANCE,
    }
    first = tmp_path / "first.md"
    second = tmp_path / "second.md"
    assert _run_cli(first, **common) == 0
    assert _run_cli(second, **common) == 0
    assert first.read_text(encoding="utf-8") == second.read_text(encoding="utf-8")


def test_s2v3_offline_smoke_records_the_provider_matrix(tmp_path: Path) -> None:
    if not S2V3_CORPUS.exists():
        pytest.skip("s2v3 corpus not ready")
    # The Setup section must carry the M3 PR-1/PR-2 provider-matrix fields
    # (provider identity plus its diagnostic source) on the second-corpus
    # report path, not only on the default pydoc-stdlib path.
    report_path = tmp_path / "S2V3_REPORT.md"
    code = _run_cli(
        report_path,
        ingests=5,
        max_queries=6,
        corpus=S2V3_CORPUS,
        queries=S2V3_QUERIES,
        maintenance=S2V3_MAINTENANCE,
    )
    assert code == 0
    text = report_path.read_text(encoding="utf-8")
    assert "Embedding provider: `lexical-hash-256` (default offline)" in text
    assert "Generation provider: `extractive-3` (default offline)" in text


def test_s2v3_offline_smoke_generation_fidelity_targeter_exits_zero_and_is_deterministic(
    tmp_path: Path,
) -> None:
    # M4: the pre-registered smoke command adds --fidelity-targeter generation
    # on the second corpus. Local providers keep it offline and deterministic,
    # but the drift probe must route through GenerationClaimTargeter and record
    # that identity, not silently fall back to the lexical default.
    if not S2V3_CORPUS.exists():
        pytest.skip("s2v3 corpus not ready")
    common = {
        "ingests": 5,
        "max_queries": 6,
        "corpus": S2V3_CORPUS,
        "queries": S2V3_QUERIES,
        "maintenance": S2V3_MAINTENANCE,
        "fidelity_targeter": "generation",
    }
    first = tmp_path / "first.md"
    second = tmp_path / "second.md"
    assert _run_cli(first, **common) == 0
    assert _run_cli(second, **common) == 0
    text = first.read_text(encoding="utf-8")
    assert first.read_text(encoding="utf-8") == second.read_text(encoding="utf-8")
    assert "Fidelity targeter: `generation:extractive-3`" in text


def test_s2v3_full_scale_run_without_real_providers_warns_instead_of_a_silent_verdict(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    if not S2V3_CORPUS.exists():
        pytest.skip("s2v3 corpus not ready")
    # Mirrors test_full_scale_run_without_real_providers_warns_instead_of_a_silent_verdict
    # on the second corpus: the S2-v3 path is the one the paper's Gate-0
    # claims are pinned to, so a full-scale (>=MIN_INGESTS) local-provider
    # attempt against it must not silently drift into a recorded verdict
    # either -- it has to loudly warn and mark the report INVALID.
    report_path = tmp_path / "report.md"
    code = _run_cli(
        report_path,
        ingests=50,
        max_queries=6,
        corpus=S2V3_CORPUS,
        queries=S2V3_QUERIES,
        maintenance=S2V3_MAINTENANCE,
    )
    assert code == 0
    assert "NOT a valid Gate-0 verdict" in capsys.readouterr().err
    text = report_path.read_text(encoding="utf-8")
    assert "**Verdict: INVALID (local providers)**" in text
