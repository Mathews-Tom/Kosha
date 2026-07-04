"""Cross-linker relate surface: discover inter-concept links.

The relate step is one of the contained LLM surfaces of the maintenance loop
(system_design §2.2 "Cross-linker: LLM relate + path validation"). It proposes,
for a concept, the other concepts it should link to; the deterministic spine then
validates and inserts those as bundle-relative Markdown links (PR-2).

Like every model-backed surface here it is split into a deterministic default and
an LLM variant behind one :class:`Relator` protocol:

* :class:`LexicalRelator` relates two concepts on lexical/tag overlap above a
  threshold — offline, reproducible, the CI/test default.
* :class:`GenerationRelator` prompts a :class:`~kosha.providers.base.GenerationProvider`
  and parses the chosen candidates, so a real model can catch semantic relations
  the lexical overlap misses.

``discover_relations`` runs a relator over a whole bundle, proposing only *new*
edges (a target a source does not already link to), in deterministic order.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from kosha.model import Bundle, Concept
from kosha.providers.base import GenerationProvider
from kosha.providers.tokens import tokenize

_NONE = "none"


@dataclass(frozen=True)
class Relation:
    """A discovered directed edge: ``source`` should link to ``target``.

    Both are concept ids (a bundle-relative path minus ``.md``). A relation whose
    ``target`` is absent from the bundle is an *intentionally dangling* link, kept
    rather than dropped (OKF §6.4 permissive consumption).
    """

    source: str
    target: str


class Relator(Protocol):
    """Decides which other concepts a source concept relates to (and should link)."""

    @property
    def name(self) -> str:
        """Stable identifier recorded in eval reports (e.g. ``lexical-overlap``)."""
        ...

    def relate(self, source: Concept, candidates: Sequence[Concept]) -> list[str]:
        """Return candidate concept ids ``source`` should link to."""
        ...


class LexicalRelator:
    """Deterministic relator: concepts with enough term/tag overlap relate.

    The score is the Jaccard overlap of the two concepts' terms plus a small bonus
    per shared tag. Candidates scoring at or above ``threshold`` relate, ranked by
    score (ties broken by concept id) and capped at ``max_links``.
    """

    def __init__(self, *, threshold: float = 0.12, max_links: int = 5) -> None:
        self._threshold = threshold
        self._max_links = max_links

    @property
    def name(self) -> str:
        return "lexical-overlap"

    def relate(self, source: Concept, candidates: Sequence[Concept]) -> list[str]:
        scored: list[tuple[float, str]] = []
        source_terms = set(tokenize(concept_text(source)))
        source_tags = {tag.lower() for tag in source.frontmatter.tags}
        for candidate in candidates:
            if candidate.concept_id == source.concept_id:
                continue
            score = term_overlap_score(source_terms, source_tags, candidate)
            if score >= self._threshold:
                scored.append((score, candidate.concept_id))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [concept_id for _, concept_id in scored[: self._max_links]]


class GenerationRelator:
    """LLM relator: prompt a generation provider and parse the chosen candidates."""

    def __init__(self, provider: GenerationProvider, *, max_links: int = 5) -> None:
        self._provider = provider
        self._max_links = max_links

    @property
    def name(self) -> str:
        return f"generation:{self._provider.name}"

    def relate(self, source: Concept, candidates: Sequence[Concept]) -> list[str]:
        others = [c for c in candidates if c.concept_id != source.concept_id]
        if not others:
            return []
        query, context = build_relate_prompt(source, others)
        generation = self._provider.generate(query, context)
        return parse_relations(generation.text, others)[: self._max_links]


def build_relate_prompt(source: Concept, candidates: Sequence[Concept]) -> tuple[str, str]:
    """Return the (query, context) pair posed to the generation provider.

    The context numbers the candidates 1..N; the model answers with the numbers of
    the concepts ``source`` relates to (or ``none``), parsed by :func:`parse_relations`.
    """
    title = source.frontmatter.title or source.concept_id
    description = source.frontmatter.description or ""
    query = (
        f"Which numbered concepts does the concept '{title}' relate to? "
        f"{description}\nAnswer with the numbers, comma-separated, or 'none'."
    )
    lines = [
        _candidate_line(index, candidate)
        for index, candidate in enumerate(candidates, start=1)
    ]
    return query, "\n".join(lines)


def parse_relations(text: str, candidates: Sequence[Concept]) -> list[str]:
    """Parse 1-based candidate numbers from a provider response into concept ids.

    Numbers out of range, ``none``, and non-numeric tokens are ignored; the result
    is de-duplicated in first-seen order.
    """
    if _NONE in text.strip().lower():
        return []
    seen: list[str] = []
    for token in tokenize(text):
        if not token.isdigit():
            continue
        index = int(token)
        if 1 <= index <= len(candidates):
            concept_id = candidates[index - 1].concept_id
            if concept_id not in seen:
                seen.append(concept_id)
    return seen


def discover_relations(bundle: Bundle, relator: Relator) -> list[Relation]:
    """Discover new directed edges across the whole bundle, deterministically.

    Concepts are visited in sorted id order, each related against every other
    concept. A proposed target the source already links to (``out_links``) is
    skipped, so re-running over an already-linked bundle proposes nothing.
    """
    concepts = [bundle.concepts[cid] for cid in sorted(bundle.concepts)]
    relations: list[Relation] = []
    for source in concepts:
        existing = set(source.out_links)
        for target in relator.relate(source, concepts):
            if target == source.concept_id or target in existing:
                continue
            relations.append(Relation(source=source.concept_id, target=target))
            existing.add(target)
    return relations


def concept_text(concept: Concept) -> str:
    parts = [
        concept.frontmatter.title or "",
        concept.frontmatter.description or "",
        concept.body,
    ]
    return " ".join(part for part in parts if part)


def _candidate_line(index: int, candidate: Concept) -> str:
    label = candidate.frontmatter.title or candidate.concept_id
    description = candidate.frontmatter.description or ""
    return f"{index}. {label} — {description}".rstrip(" —") if description else f"{index}. {label}"


def term_overlap_score(source_terms: set[str], source_tags: set[str], candidate: Concept) -> float:
    candidate_terms = set(tokenize(concept_text(candidate)))
    union = source_terms | candidate_terms
    jaccard = len(source_terms & candidate_terms) / len(union) if union else 0.0
    candidate_tags = {tag.lower() for tag in candidate.frontmatter.tags}
    tag_bonus = 0.1 * len(source_tags & candidate_tags)
    return jaccard + tag_bonus
