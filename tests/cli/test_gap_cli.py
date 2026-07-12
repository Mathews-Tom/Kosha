"""``kosha gap scan|list|show|answer|invalidate|stale`` at the CLI layer (M10)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from kosha.cli import main
from kosha.evidence import CoverageKind, SourceCoverage
from kosha.gaps import GapLedgerStore, dedup_key, gaps_root
from kosha.gaps.model import GapKind
from kosha.git_store import GitStore
from kosha.pipeline import ingest

_ASOF = datetime(2026, 6, 28, tzinfo=UTC)


def _seed_bundle(tmp_path: Path) -> tuple[Path, GitStore]:
    bundle = tmp_path / "bundle"
    (bundle / "policies").mkdir(parents=True)
    (bundle / "policies" / "returns.md").write_text(
        "---\ntype: policy\ntitle: Returns\n"
        "description: When and how customers may return products.\n---\n"
        "Standard returns are accepted within 30 days of delivery.\n",
        encoding="utf-8",
    )
    store = GitStore.init(bundle)
    store.commit(["policies/returns.md"], "chore: seed")
    return bundle, store


def _policy_update_source(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    (source / "policies").mkdir(parents=True)
    (source / "policies" / "returns.md").write_text(
        "# Returns\n\nStandard returns are accepted within 60 days of delivery.\n",
        encoding="utf-8",
    )
    return source


def _add_legacy_commit(bundle: Path, store: GitStore) -> None:
    (bundle / "policies" / "shipping.md").write_text(
        "---\ntype: policy\ntitle: Shipping\n---\nShips within 3 days.\n", encoding="utf-8"
    )
    store.commit(
        ["policies/shipping.md"],
        "feat(kosha): ingest legacy\n\n- create policies/shipping.md",
    )


def _add_windowed_coverage_commit(tmp_path: Path, bundle: Path, store: GitStore) -> None:
    result = ingest(
        _policy_update_source(tmp_path),
        bundle,
        asof=_ASOF,
        source_authority=10,
        git_store=store,
        branch="ingest/windowed",
        coverage=SourceCoverage(kind=CoverageKind.WINDOWED, scope="last 24h"),
    )
    assert result.committed is True


def test_gap_with_no_subcommand_prints_usage_and_exits_2(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = main(["gap"])
    assert code == 2
    assert "scan, list, show, answer, invalidate, stale" in capsys.readouterr().err


def test_gap_scan_rejects_a_missing_bundle_directory(tmp_path: Path) -> None:
    code = main(["gap", "scan", str(tmp_path / "nope")])
    assert code == 2


def test_gap_scan_reports_two_categories_and_merges_the_ledger(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle, store = _seed_bundle(tmp_path)
    _add_legacy_commit(bundle, store)
    _add_windowed_coverage_commit(tmp_path, bundle, store)

    code = main(["gap", "scan", str(bundle)])

    assert code == 0
    out = capsys.readouterr().out
    assert "incomplete_coverage" in out
    assert "legacy_evidence" in out
    ledger = GapLedgerStore(gaps_root(bundle)).load()
    assert {gap.kind for gap in ledger} == {GapKind.LEGACY_EVIDENCE, GapKind.INCOMPLETE_COVERAGE}


def test_gap_scan_json_reports_categories_and_ledger(tmp_path: Path) -> None:
    bundle, store = _seed_bundle(tmp_path)
    _add_legacy_commit(bundle, store)

    code = main(["gap", "scan", str(bundle), "--json"])

    assert code == 0


def test_gap_scan_is_idempotent_a_repeat_scan_deduplicates_not_duplicates(
    tmp_path: Path,
) -> None:
    bundle, store = _seed_bundle(tmp_path)
    _add_legacy_commit(bundle, store)

    main(["gap", "scan", str(bundle)])
    main(["gap", "scan", str(bundle)])

    ledger = GapLedgerStore(gaps_root(bundle)).load()
    assert len(ledger) == 1
    assert ledger[0].seen_count == 2


def test_gap_list_with_no_ledger_reports_nothing_recorded(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle, _ = _seed_bundle(tmp_path)
    code = main(["gap", "list", str(bundle)])
    assert code == 0
    assert "no knowledge gaps recorded" in capsys.readouterr().out


def test_gap_list_json_lists_scanned_gaps(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle, store = _seed_bundle(tmp_path)
    _add_legacy_commit(bundle, store)
    main(["gap", "scan", str(bundle)])
    capsys.readouterr()

    code = main(["gap", "list", str(bundle), "--json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["gaps"]) == 1
    assert payload["gaps"][0]["kind"] == "legacy_evidence"


def test_gap_list_filters_by_status(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bundle, store = _seed_bundle(tmp_path)
    _add_legacy_commit(bundle, store)
    main(["gap", "scan", str(bundle)])
    ledger = GapLedgerStore(gaps_root(bundle)).load()
    gap_id = ledger[0].gap_id
    main(["gap", "answer", str(bundle), gap_id, "--resolution", "c" * 64])
    capsys.readouterr()

    code = main(["gap", "list", str(bundle), "--status", "open", "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["gaps"] == []

    code = main(["gap", "list", str(bundle), "--status", "answered", "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["gaps"]) == 1


def test_gap_show_an_unknown_gap_id_fails_loud(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle, _ = _seed_bundle(tmp_path)
    code = main(["gap", "show", str(bundle), "a" * 64])
    assert code == 1
    assert "no such gap" in capsys.readouterr().err


def test_gap_show_renders_a_scanned_gap(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle, store = _seed_bundle(tmp_path)
    _add_legacy_commit(bundle, store)
    main(["gap", "scan", str(bundle)])
    gap_id = GapLedgerStore(gaps_root(bundle)).load()[0].gap_id
    capsys.readouterr()

    code = main(["gap", "show", str(bundle), gap_id])

    assert code == 0
    out = capsys.readouterr().out
    assert gap_id in out
    assert "legacy_evidence" in out


def test_gap_answer_transitions_the_gap_and_persists_the_resolution(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle, store = _seed_bundle(tmp_path)
    _add_legacy_commit(bundle, store)
    main(["gap", "scan", str(bundle)])
    gap_id = GapLedgerStore(gaps_root(bundle)).load()[0].gap_id
    capsys.readouterr()

    code = main(["gap", "answer", str(bundle), gap_id, "--resolution", "c" * 64])

    assert code == 0
    assert "answered" in capsys.readouterr().out
    reloaded = GapLedgerStore(gaps_root(bundle)).load()[0]
    assert reloaded.status.value == "answered"
    assert reloaded.resolution_reference == "c" * 64


def test_gap_invalidate_transitions_the_gap(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle, store = _seed_bundle(tmp_path)
    _add_legacy_commit(bundle, store)
    main(["gap", "scan", str(bundle)])
    gap_id = GapLedgerStore(gaps_root(bundle)).load()[0].gap_id
    capsys.readouterr()

    code = main(["gap", "invalidate", str(bundle), gap_id, "--resolution", "reviewed: no gap"])

    assert code == 0
    reloaded = GapLedgerStore(gaps_root(bundle)).load()[0]
    assert reloaded.status.value == "invalidated"


def test_gap_stale_transitions_the_gap_without_a_resolution_flag(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle, store = _seed_bundle(tmp_path)
    _add_legacy_commit(bundle, store)
    main(["gap", "scan", str(bundle)])
    gap_id = GapLedgerStore(gaps_root(bundle)).load()[0].gap_id
    capsys.readouterr()

    code = main(["gap", "stale", str(bundle), gap_id])

    assert code == 0
    reloaded = GapLedgerStore(gaps_root(bundle)).load()[0]
    assert reloaded.status.value == "stale"


def test_gap_answer_on_an_already_answered_gap_fails_loud(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle, store = _seed_bundle(tmp_path)
    _add_legacy_commit(bundle, store)
    main(["gap", "scan", str(bundle)])
    gap_id = GapLedgerStore(gaps_root(bundle)).load()[0].gap_id
    main(["gap", "answer", str(bundle), gap_id, "--resolution", "c" * 64])
    capsys.readouterr()

    code = main(["gap", "answer", str(bundle), gap_id, "--resolution", "d" * 64])

    assert code == 1
    assert "already" in capsys.readouterr().err


def test_gap_answer_on_an_unknown_gap_id_fails_loud(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle, _ = _seed_bundle(tmp_path)
    code = main(["gap", "answer", str(bundle), "a" * 64, "--resolution", "c" * 64])
    assert code == 1
    assert "no such gap" in capsys.readouterr().err


def test_gap_ids_are_stable_across_producer_and_ledger(tmp_path: Path) -> None:
    bundle, store = _seed_bundle(tmp_path)
    _add_legacy_commit(bundle, store)
    main(["gap", "scan", str(bundle)])
    ledger = GapLedgerStore(gaps_root(bundle)).load()
    commit_sha = store.current_sha("HEAD")
    assert ledger[0].gap_id == dedup_key(GapKind.LEGACY_EVIDENCE, commit_sha)
