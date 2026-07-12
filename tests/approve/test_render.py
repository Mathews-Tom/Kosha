"""render_change_item / render_flag_item: per-item review rendering (M8 PR-3)."""

from __future__ import annotations

from kosha.approve import ChangeRouting, Lane, render_change_item, render_flag_item, render_plan
from kosha.evidence import CoverageKind, SourceCoverage
from kosha.plan import ChangeKind, ChangePlan, FileChange, Flag


def _change(path: str, **overrides: object) -> FileChange:
    defaults: dict[str, object] = {
        "path": path,
        "kind": ChangeKind.CREATE,
        "content": "x",
        "summary": "",
    }
    defaults.update(overrides)
    return FileChange.model_validate(defaults)


def test_render_change_item_shows_path_kind_and_provenance() -> None:
    change = _change("policies/returns.md", summary="new concept: Returns", confidence=0.82)
    text = render_change_item(change)
    assert "[create] policies/returns.md" in text
    assert "summary: new concept: Returns" in text
    assert "conf=0.82" in text


def test_render_change_item_includes_route_lane_and_reason_when_routed() -> None:
    change = _change("policies/returns.md")
    route = ChangeRouting(change, Lane.SKIM, "ambiguous dedup confidence")
    text = render_change_item(change, route)
    assert "lane=skim (ambiguous dedup confidence)" in text


def test_render_change_item_omits_lane_line_when_unrouted() -> None:
    text = render_change_item(_change("a.md"))
    assert "lane=" not in text


def test_render_flag_item_shows_concept_and_summary() -> None:
    flag = Flag(
        concept_id="policies/returns", summary="temporal conflict", detail="two claims disagree"
    )
    text = render_flag_item(flag)
    assert "[flag] policies/returns: temporal conflict" in text
    assert "two claims disagree" in text


def test_render_flag_item_omits_detail_line_when_blank() -> None:
    flag = Flag(concept_id="policies/returns", summary="conflict")
    text = render_flag_item(flag)
    assert text == "[flag] policies/returns: conflict"


# --- coverage: non-complete surfaces beside the change (DEVELOPMENT_PLAN.md M5) -


def test_render_change_item_shows_non_complete_coverage() -> None:
    change = _change(
        "sources/feed.md",
        coverage=SourceCoverage(kind=CoverageKind.WINDOWED, scope="last 24h of the feed"),
    )
    text = render_change_item(change)
    assert "coverage=windowed" in text


def test_render_change_item_omits_coverage_annotation_when_complete() -> None:
    change = _change(
        "sources/feed.md",
        coverage=SourceCoverage(kind=CoverageKind.COMPLETE, scope="one file snapshot"),
    )
    text = render_change_item(change)
    assert "coverage=" not in text


def test_render_change_item_omits_coverage_annotation_when_no_evidence_link() -> None:
    text = render_change_item(_change("index.md"))
    assert "coverage=" not in text


def test_render_change_item_shows_coverage_warnings_with_no_secret_leakage() -> None:
    change = _change(
        "sources/feed.md",
        coverage=SourceCoverage(
            kind=CoverageKind.BEST_EFFORT,
            truncated=True,
            warnings=("stopped after the configured byte cap; more content may remain",),
        ),
    )
    text = render_change_item(change)
    assert "coverage warning: stopped after the configured byte cap" in text
    assert "AKIA" not in text
    assert "secret" not in text.lower()


def test_render_change_item_omits_coverage_warning_lines_when_none_recorded() -> None:
    change = _change(
        "sources/feed.md", coverage=SourceCoverage(kind=CoverageKind.COMPLETE)
    )
    text = render_change_item(change)
    assert "coverage warning" not in text


def test_render_plans_summary_line_also_shows_non_complete_coverage() -> None:
    change = _change(
        "sources/feed.md",
        kind=ChangeKind.UPDATE,
        coverage=SourceCoverage(kind=CoverageKind.CURSOR_INCREMENTAL),
    )
    text = render_plan(ChangePlan(changes=[change]))
    assert "coverage=cursor_incremental" in text
