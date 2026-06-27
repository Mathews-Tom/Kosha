"""Route a dedup :class:`~kosha.dedup.resolver.Decision` to the M7 writer.

This is the seam between the dedup resolver (M6) and the merge/writer (M7): a
terminal UPDATE goes through the claim-targeted body merge against the matched
concept, and a terminal CREATE mints a new concept. A SPLIT is not a leaf write —
the resolver already re-resolved it into ``decision.parts``; the caller applies
each part — so handing a SPLIT here raises rather than silently dropping it.
"""

from __future__ import annotations

from datetime import datetime

from kosha.dedup import Action, Decision
from kosha.extract import ConceptDraft
from kosha.merge.create import create_concept
from kosha.merge.update import ClaimTargeter, merge_update
from kosha.model import Concept, Source


def apply_decision(
    decision: Decision,
    draft: ConceptDraft,
    *,
    existing: Concept | None,
    source: Source,
    asserted_at: datetime,
    targeter: ClaimTargeter,
    new_concept_id: str | None = None,
) -> Concept:
    """Apply a terminal dedup decision through the claim layer.

    ``existing`` is required for UPDATE (the concept named by the decision);
    ``new_concept_id`` is required for CREATE (the path the draft becomes). A
    SPLIT decision is not directly applicable — iterate ``decision.parts``.
    """
    if decision.action is Action.UPDATE:
        if existing is None:
            raise ValueError("UPDATE requires the existing concept to merge into")
        return merge_update(existing, draft, source, asserted_at, targeter=targeter)
    if decision.action is Action.CREATE:
        concept_id = new_concept_id or decision.concept_id
        if concept_id is None:
            raise ValueError("CREATE requires a new_concept_id")
        return create_concept(draft, concept_id, source, asserted_at)
    raise ValueError(f"cannot apply a {decision.action.value} decision; resolve its parts first")
