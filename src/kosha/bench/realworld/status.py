"""Render the tracked Gate-0 status doc update from a real-world report (M3).

`docs/gate0-status.md`'s "current public verdict" sentence and evidence table
were hand-authored prose after each prior Gate-0 run (M1) — nothing tied the
doc text to what a run actually measured, so the docs could silently drift
from the report. :func:`render_gate_status_summary` and
:func:`render_gate_status_row` turn a :class:`RealworldReport` into that exact
text, so recording a new run's verdict is generating and pasting this output,
not freehand prose, and `test_gate0_status_matches_current_verdict` in
`tests/docs/test_public_claims.py` keeps the checked-in doc from drifting away
from it.
"""

from __future__ import annotations

from kosha.bench.realworld.runner import SAFETY_MARGIN, RealworldReport


def render_gate_status_summary(report: RealworldReport) -> str:
    """Render the `docs/gate0-status.md` "Current public verdict" sentence."""
    if report.verdict == "GO":
        return (
            "**Real-model Gate-0 verdict: GO.** The maintenance loop preserves "
            "knowledge integrity under contradiction better than a "
            "safety-instructed prompt-only baseline; M14+ product expansion may "
            "proceed."
        )
    return (
        "**Real-model Gate-0 verdict: NO-GO.** Kosha ships as an OSS governance "
        "skill. M14+ product expansion remains halted unless a later "
        "pre-registered real-model Gate-0 run records a GO verdict."
    )


def render_gate_status_row(
    report: RealworldReport, *, run_label: str, commit: str, date: str
) -> str:
    """Render one `docs/gate0-status.md` evidence-table row for this run."""
    loop_safety = report.safety_by_name("kosha_loop")
    prompt_safety = report.safety_by_name("prompt_only")
    setup = (
        f"{report.embedding_provider} + {report.generation_provider}, "
        f"{report.concept_count}-concept corpus, {report.drift.ingests} sequential ingests"
    )
    result = (
        f"**{report.verdict}** — loop safety {loop_safety.safety_rate:.2f} vs "
        f"prompt-only {prompt_safety.safety_rate:.2f} (delta {report.safety_delta:+.2f}, "
        f"margin {SAFETY_MARGIN:.2f}); loop silent overwrites {loop_safety.silent_overwrites}"
    )
    return f"| {run_label} (`{commit}`, {date}) | {setup} | {result} |"
