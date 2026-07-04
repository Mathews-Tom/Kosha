"""Pipeline: the end-to-end ingest loop behind the plan -> approve -> commit gate.

The pipeline package wires every producer milestone (M5 through M9) into one ``ingest``
entrypoint and gates its writes through the governance surface (M10): a
:class:`~kosha.plan.ChangePlan` routed by graduated autonomy, approved (delegated
or explicit), then committed on a branch with a daily backup (system_design §4.1,
§4.5, §6).
"""

from __future__ import annotations

from kosha.pipeline.run import IngestResult, commit_plan, commit_reviewed_plan, decide_plan, ingest
from kosha.pipeline.writer import UpdateResult, apply_update, hydrate_claims, new_concept_id

__all__ = [
    "IngestResult",
    "UpdateResult",
    "apply_update",
    "commit_plan",
    "commit_reviewed_plan",
    "decide_plan",
    "hydrate_claims",
    "ingest",
    "new_concept_id",
]
