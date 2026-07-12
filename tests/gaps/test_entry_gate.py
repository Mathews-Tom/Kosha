"""DEVELOPMENT_PLAN.md M10 hard entry gate.

Proves -- from real, deterministic, committed-history fixtures, not
documentation or a model's say-so -- that at least two objective gap
categories from ``.docs/memory-and-openwiki-enhancement-plan.md`` §17 exist
before any :mod:`kosha.gaps` lifecycle code is allowed to ship:

- ``legacy_evidence``: an ingest commit missing a ``Source-Run``/
  ``Evidence-SHA256`` trailer (M3's ``evidence_status == "legacy"``,
  reachable in real history whenever a bundle predates M3, or a connector
  mints no evidence-bound claim).
- ``incomplete_coverage``: a change whose evidence carries a non-``complete``
  :class:`~kosha.evidence.model.SourceCoverage.kind` (M5's
  ``incomplete_coverage_count`` -- real for every bounded/windowed/cursor/
  sampled/best-effort adapter run, including the M7 Git and MCP connectors
  already merged to ``main``).

Both signals are computed by :func:`kosha.audit.export.build_report`, the
same deterministic audit-export machinery ``kosha audit export`` already
ships; this test only proves the categories are real and reachable, and
that :mod:`kosha.gaps.produce` faithfully turns them into gap events.

Verification: ``uv run pytest -q tests/gaps/test_entry_gate.py`` exits 0 and
this module prints the evidenced category list.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from kosha.audit import build_report
from kosha.evidence import CoverageKind, SourceCoverage
from kosha.gaps.model import GapKind
from kosha.gaps.produce import evidenced_categories, gaps_from_compliance_report
from kosha.git_store import GitStore
from kosha.pipeline import ingest

_ASOF = datetime(2026, 6, 28, tzinfo=UTC)
_AT = datetime(2026, 7, 12, tzinfo=UTC)

_REQUIRED_MINIMUM_CATEGORIES = 2


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


def _entry_gate_bundle(tmp_path: Path) -> Path:
    """Build a small bundle whose real, git-committed history carries both
    entry-gate categories -- one pre-M3-shaped ("legacy") ingest commit with
    no evidence trailer, and one M5 windowed-coverage ingest commit -- the
    same two shapes real M3/M5/M7 operation already produces.
    """
    bundle, store = _seed_bundle(tmp_path)

    # Category 1: legacy_evidence -- an ingest-shaped commit with no
    # Source-Run/Evidence-SHA256 trailer, exactly what a pre-M3 bundle or a
    # connector run that mints no evidence-bound claim leaves behind
    # (kosha.audit.export.CommitRecord.evidence_status == "legacy").
    (bundle / "policies" / "shipping.md").write_text(
        "---\ntype: policy\ntitle: Shipping\n---\nShips within 3 days.\n", encoding="utf-8"
    )
    store.commit(
        ["policies/shipping.md"],
        "feat(kosha): ingest legacy\n\n- create policies/shipping.md",
    )

    # Category 2: incomplete_coverage -- a real ingest through the M3/M5
    # pipeline whose evidence carries a non-"complete" SourceCoverage.kind,
    # exactly what the already-merged M7 Git/MCP connectors record for a
    # bounded or cursor-incremental run.
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

    return bundle


def test_committed_history_evidences_at_least_two_objective_gap_categories(
    tmp_path: Path,
) -> None:
    bundle = _entry_gate_bundle(tmp_path)

    report = build_report(bundle)
    # The same deterministic counts kosha audit export already reports --
    # proof the categories are real signals, not invented for this test.
    assert report.legacy_provenance_count >= 1
    assert report.incomplete_coverage_count >= 1

    events = gaps_from_compliance_report(report, at=_AT)
    categories = evidenced_categories(events)

    print(f"M10 entry gate: evidenced categories = {sorted(c.value for c in categories)}")

    assert categories >= {GapKind.LEGACY_EVIDENCE, GapKind.INCOMPLETE_COVERAGE}
    assert len(categories) >= _REQUIRED_MINIMUM_CATEGORIES


def test_the_evidenced_categories_trace_to_named_gap_events_not_raw_counts(
    tmp_path: Path,
) -> None:
    # The entry gate requires *events a producer can act on*, not just two
    # report counters -- prove each category has a concrete, inspectable
    # KnowledgeGap event with a deterministic reason code attached.
    bundle = _entry_gate_bundle(tmp_path)
    report = build_report(bundle)
    events = gaps_from_compliance_report(report, at=_AT)

    by_kind = {event.kind: event for event in events}
    assert GapKind.LEGACY_EVIDENCE in by_kind
    assert GapKind.INCOMPLETE_COVERAGE in by_kind
    assert by_kind[GapKind.LEGACY_EVIDENCE].reason_code is not None
    assert by_kind[GapKind.INCOMPLETE_COVERAGE].reason_code is not None
