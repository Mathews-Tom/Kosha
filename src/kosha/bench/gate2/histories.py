"""At-scale conflict contexts for the Gate-0 v2 re-test (spike S2).

The M13 contradictions were six clean, single-claim cases a good prompt handles
as easily as the loop. The loop's structural win should surface where a prompt's
best-effort breaks: when the conflicting prior is *buried* — one clause deep in a
long body, or one claim among a deep supersede/append history. These builders
produce those at-scale contexts deterministically so the held-out set spans them.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from kosha.merge import make_claim
from kosha.model import Claim

# A fixed epoch so every generated history is byte-reproducible.
EPOCH = datetime(2026, 1, 1, tzinfo=UTC)


def deep_history_claims(
    subject: str,
    prior: str,
    depth: int,
    *,
    start: datetime = EPOCH,
    step: timedelta = timedelta(days=1),
) -> list[Claim]:
    """``depth`` benign in-force claims about ``subject`` with ``prior`` buried among them.

    Every claim is ``current`` (an append-only history of distinct facets, not a
    supersede chain), so a decider must scan the whole in-force set to find the
    one claim ``prior`` that an incoming statement conflicts with — the deep-
    history at-scale regime. ``prior`` is placed near the middle, not last, so a
    decider that only checks the head misses it.
    """
    if depth < 1:
        raise ValueError("depth must be >= 1")
    facets = [
        make_claim(
            _facet(subject, i),
            "corpus",
            start + step * i,
            effective_from=start + step * i,
        )
        for i in range(depth)
    ]
    prior_claim = make_claim(prior, "corpus", start, effective_from=start)
    facets.insert(depth // 2, prior_claim)
    return facets


def render_history(claims: Sequence[Claim]) -> str:
    """Render an in-force claim set as the body text a prompt-only baseline reads."""
    return "\n".join(f"- {claim.statement}" for claim in claims)


def bury_in_body(fact: str, *, sentences: int) -> str:
    """Embed ``fact`` in ``sentences`` lines of distinct filler, returning the body.

    The conflicting fact sits in the middle of a long, lexically unrelated body,
    so subject overlap against an incoming statement is diluted — the buried-body
    at-scale regime that a whole-body Jaccard signal struggles with.
    """
    if sentences < 0:
        raise ValueError("sentences must be >= 0")
    head = [_filler(i) for i in range(sentences // 2)]
    tail = [_filler(i + sentences // 2) for i in range(sentences - sentences // 2)]
    return " ".join([*head, fact, *tail])


def _facet(subject: str, index: int) -> str:
    # Distinct, benign facets that share the subject but no conflict cue, so they
    # neither false-trigger the detector nor accidentally match an incoming claim.
    aspects = (
        "is documented in the reference",
        "has stable public behavior",
        "is covered by the regression suite",
        "appears in the module index",
        "carries an example in its docstring",
        "is importable without side effects",
        "preserves its call signature",
        "is referenced by sibling concepts",
    )
    return f"{subject} {aspects[index % len(aspects)]} (note {index})."


def _filler(index: int) -> str:
    topics = (
        "Background context", "Usage notes", "Related guidance", "Historical detail",
        "Implementation aside", "Compatibility remark", "Style preference", "Cross reference",
    )
    return f"{topics[index % len(topics)]} number {index} adds unrelated narrative."
