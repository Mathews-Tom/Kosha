"""Decision audit log — score + rationale for every dedup decision.

system_design §4.3 and overview §6 require every dedup decision to log a
similarity score and a rationale: the maintenance-loop telemetry the dedup eval
and human review read. :func:`record_decisions` flattens a resolver
:class:`~kosha.dedup.resolver.Decision` (and the child decisions of a SPLIT) into
one record per outcome; :func:`render_decision_log` renders them as a stable,
greppable audit trail. No files are written here (M7 owns persistence).
"""

from __future__ import annotations

from dataclasses import dataclass

from kosha.dedup.resolver import Decision
from kosha.extract import ConceptDraft


@dataclass(frozen=True)
class DecisionRecord:
    """One audited dedup decision: what happened, to which concept, and why."""

    draft_title: str
    source_id: str
    action: str
    concept_id: str | None
    score: float
    adjudicated: bool
    rationale: str


def record_decisions(draft: ConceptDraft, decision: Decision) -> list[DecisionRecord]:
    """Flatten a decision (and any SPLIT children) into audit records.

    A SPLIT records the parent decision followed by one record per re-resolved
    child, so the trail shows both the split and what each piece became.
    """
    records = [_record(draft.title, draft.source_id, decision)]
    records.extend(
        _record(f"{draft.title} (split)", draft.source_id, part)
        for part in decision.parts
    )
    return records


def render_decision_log(records: list[DecisionRecord]) -> str:
    """Render audit records as one deterministic line per decision."""
    lines = []
    for record in records:
        target = record.concept_id or "-"
        lane = "llm" if record.adjudicated else "auto"
        lines.append(
            f"{record.action.upper():6} {target:40} score={record.score:.3f} "
            f"[{lane}] {record.draft_title} :: {record.rationale}"
        )
    return "\n".join(lines)


def _record(title: str, source_id: str, decision: Decision) -> DecisionRecord:
    return DecisionRecord(
        draft_title=title,
        source_id=source_id,
        action=decision.action.value,
        concept_id=decision.concept_id,
        score=decision.score,
        adjudicated=decision.adjudicated,
        rationale=decision.rationale,
    )
