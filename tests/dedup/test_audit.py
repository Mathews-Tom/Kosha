"""Tests for the dedup decision audit log."""

from __future__ import annotations

from pathlib import Path

from kosha.dedup import Action, LexicalAdjudicator
from kosha.dedup.audit import record_decisions, render_decision_log
from kosha.dedup.resolver import Decision, resolve_draft
from kosha.extract import ConceptDraft
from kosha.index import EmbeddingIndex
from kosha.index.embedding import index_text
from kosha.okf import load_bundle
from kosha.providers import LexicalEmbeddingProvider

NORTHWIND = Path(__file__).resolve().parents[2] / "bundles" / "northwind"


def _draft(title: str = "draft") -> ConceptDraft:
    return ConceptDraft(title=title, body="b", description="d", type="t", source_id="src://1")


def test_a_simple_decision_logs_one_record_with_score_and_rationale() -> None:
    decision = Decision(Action.UPDATE, "policies/refunds", 0.97, "score 0.970 >= high 0.95")
    [record] = record_decisions(_draft(), decision)
    assert record.action == "update"
    assert record.concept_id == "policies/refunds"
    assert record.score == 0.97
    assert record.adjudicated is False
    assert record.rationale
    assert record.source_id == "src://1"


def test_a_split_logs_the_parent_and_each_child() -> None:
    parts = (
        Decision(Action.CREATE, None, 0.3, "child novel", adjudicated=True),
        Decision(Action.UPDATE, "entities/order", 0.4, "child match", adjudicated=True),
    )
    decision = Decision(
        Action.SPLIT, None, 0.5, "draft mixes topics", adjudicated=True, parts=parts
    )
    records = record_decisions(_draft("bundle"), decision)
    assert [r.action for r in records] == ["split", "create", "update"]
    assert records[0].draft_title == "bundle"
    assert all(r.draft_title == "bundle (split)" for r in records[1:])


def test_render_decision_log_emits_one_line_per_record() -> None:
    decision = Decision(Action.CREATE, None, 0.1, "score 0.100 < low 0.15")
    rendered = render_decision_log(record_decisions(_draft(), decision))
    lines = rendered.splitlines()
    assert len(lines) == 1
    assert "CREATE" in lines[0]
    assert "score=0.100" in lines[0]
    assert "[auto]" in lines[0]


def test_every_decision_in_a_real_resolve_is_audited() -> None:
    bundle = load_bundle(NORTHWIND)
    index = EmbeddingIndex.build(bundle, LexicalEmbeddingProvider())
    concept_texts = {cid: index_text(c) for cid, c in bundle.concepts.items()}
    concept = bundle.concepts["policies/refunds"]
    draft = ConceptDraft(
        title=concept.frontmatter.title or "refunds",
        body=concept.body,
        description=concept.frontmatter.description or "",
        type=concept.frontmatter.type,
        source_id="reingest://policies/refunds",
    )
    decision = resolve_draft(draft, index, concept_texts, adjudicator=LexicalAdjudicator())
    [record] = record_decisions(draft, decision)
    assert record.action == "update"
    assert record.concept_id == "policies/refunds"
    assert record.score >= 0.95
    # The audit line is human-readable and carries the score.
    assert "score=" in render_decision_log([record])
