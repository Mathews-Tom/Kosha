"""At-scale conflict contexts: deep histories and buried bodies (spike S2)."""

from __future__ import annotations

import pytest

from kosha.bench.gate2.histories import (
    bury_in_body,
    deep_history_claims,
    render_history,
)
from kosha.model import ClaimStatus


def test_deep_history_buries_prior_among_current_claims() -> None:
    claims = deep_history_claims("json.dumps", "json.dumps returns at most 8 items.", 12)
    assert len(claims) == 13  # depth benign facets + the prior
    assert all(claim.status is ClaimStatus.CURRENT for claim in claims)
    priors = [c for c in claims if c.statement == "json.dumps returns at most 8 items."]
    assert len(priors) == 1
    # Buried, not at the head and not the tail.
    index = claims.index(priors[0])
    assert 0 < index < len(claims) - 1


def test_deep_history_rejects_zero_depth() -> None:
    with pytest.raises(ValueError, match="depth must be"):
        deep_history_claims("s", "p", 0)


def test_render_history_lists_every_statement() -> None:
    claims = deep_history_claims("re.findall", "re.findall returns all matches.", 5)
    rendered = render_history(claims)
    assert rendered.count("\n") == len(claims) - 1
    assert "re.findall returns all matches." in rendered


def test_bury_in_body_embeds_the_fact_in_filler() -> None:
    fact = "shutil.copytree preserves metadata."
    body = bury_in_body(fact, sentences=10)
    assert fact in body
    # The fact is in the middle, not at the start or end of the body.
    assert not body.startswith(fact)
    assert not body.endswith(fact)
    assert len(body) > len(fact) * 3


def test_bury_in_body_rejects_negative() -> None:
    with pytest.raises(ValueError, match="sentences must be"):
        bury_in_body("x", sentences=-1)
