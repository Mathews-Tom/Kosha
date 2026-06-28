"""Capture an approve/reject decision for a change plan.

The §1 governance invariant is "no silent mutation": a plan reaches Git only on an
explicit approval. Decision capture is therefore **default-safe** — anything that
is not a clear yes is a reject, so an empty line, a stray keystroke, or a closed
input never approves a write. The reader is injected (rather than calling
``input`` directly) so the gate is testable and the pipeline can drive it from a
flag, a prompt, or a non-interactive default.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum

# Reads one line given a prompt — ``input`` in the CLI, a stub in tests.
Reader = Callable[[str], str]

_YES = frozenset({"y", "yes"})
_NO = frozenset({"n", "no"})
_DEFAULT_PROMPT = "Approve this plan? [y/N] "


class Decision(StrEnum):
    """The outcome of the approve gate."""

    APPROVE = "approve"
    REJECT = "reject"


def parse_decision(answer: str) -> Decision | None:
    """Parse a yes/no answer; ``None`` when it is neither."""
    token = answer.strip().lower()
    if token in _YES:
        return Decision.APPROVE
    if token in _NO:
        return Decision.REJECT
    return None


def request_decision(
    reader: Reader,
    *,
    prompt: str = _DEFAULT_PROMPT,
    retries: int = 3,
) -> Decision:
    """Ask for a decision, re-prompting on an unparseable answer.

    Default-safe: after ``retries`` unparseable answers (or an empty/closed input)
    the gate rejects, so nothing is approved without a clear yes.
    """
    for _ in range(max(1, retries)):
        try:
            answer = reader(prompt)
        except EOFError:
            return Decision.REJECT
        decision = parse_decision(answer)
        if decision is not None:
            return decision
    return Decision.REJECT
