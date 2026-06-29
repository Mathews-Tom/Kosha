"""The prompt-only baseline: a good AGENTS.md plus a real LLM, no Kosha engine.

System_design R11 and KOSHA_STRATEGIC_ANALYSIS §2.4 set the bar Kosha must clear:
a competent engineer with a good ``AGENTS.md`` and an agent told to read and
maintain concept files. This baseline is exactly that, with no structured dedup,
merge, or contradiction machinery:

* :meth:`PromptOnlyBaseline.answer` finds the nearest concepts (the embedding jump
  the AGENTS fragment grants), loads their full bodies into the prompt, and lets
  the LLM answer and self-cite.
* :meth:`PromptOnlyBaseline.route` shows the LLM the nearest concept summaries and
  the new note, and asks it to decide UPDATE-an-existing or CREATE-new in one shot
  — the maintenance decision Kosha makes with embedding routing plus reserved LLM
  adjudication.

The LLM is reached only through the :class:`~kosha.providers.base.GenerationProvider`
interface, so the same baseline runs offline against a deterministic local
provider (fixture tests) and against a real model (the benchmark).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from kosha.bench.strategies import RetrievedContext
from kosha.index import EmbeddingIndex
from kosha.model import Bundle
from kosha.providers.base import Generation, GenerationProvider

# How the baseline must format its answer so cited concepts can be scored.
_ANSWER_INSTRUCTION = (
    "Answer the question using only the concepts above. On a final line, list the "
    "concept ids you used as 'CITED: id1, id2'."
)
# How the baseline must format its routing decision so it can be scored.
_ROUTE_INSTRUCTION = (
    "Decide whether the new note updates or contradicts one of the existing concepts "
    "above, or is genuinely new knowledge. Reply on a single line with exactly "
    "'UPDATE <concept_id>' (using one of the ids above) or 'CREATE'."
)
_CITED = re.compile(r"CITED:\s*(?P<ids>.+)", re.IGNORECASE)
_UPDATE = re.compile(r"\bUPDATE\b\s+(?P<id>[A-Za-z0-9/_.\-]+)", re.IGNORECASE)
_CREATE = re.compile(r"\bCREATE\b", re.IGNORECASE)


@dataclass(frozen=True)
class PromptOnlyAnswer:
    """A prompt-only answer: what reached the model, what it produced, what it cited."""

    context: RetrievedContext
    generation: Generation
    cited: tuple[str, ...]


@dataclass(frozen=True)
class PromptDecision:
    """A prompt-only maintenance routing decision."""

    action: str
    concept_id: str | None


class PromptOnlyBaseline:
    """The honest skill-not-product alternative driven by a real LLM."""

    name = "prompt_only"

    def __init__(
        self,
        bundle: Bundle,
        index: EmbeddingIndex,
        generator: GenerationProvider,
        *,
        guidance: str,
        candidate_k: int = 6,
    ) -> None:
        if candidate_k <= 0:
            raise ValueError("candidate_k must be positive")
        self._bundle = bundle
        self._index = index
        self._generator = generator
        self._guidance = guidance
        self._candidate_k = candidate_k

    def answer(self, question: str) -> PromptOnlyAnswer:
        """Answer ``question`` from the nearest loaded concept files, self-citing."""
        candidates = self._candidates(question)
        context_text = self._render_bodies(candidates)
        prompt = f"{self._guidance}\n\nQuestion: {question}\n\n{_ANSWER_INSTRUCTION}"
        generation = self._generator.generate(prompt, context_text)
        cited = _parse_cited(generation.text, set(self._bundle.concepts))
        # Concept recall is scored over what reached the model (the loaded
        # candidate files), the same basis the retrieval strategies use; citations
        # are reported but never inflate recall (a model can name an id it was not
        # shown).
        context = RetrievedContext(self.name, list(candidates), context_text, round_trips=1)
        return PromptOnlyAnswer(context=context, generation=generation, cited=tuple(cited))

    def route(self, title: str, body: str) -> PromptDecision:
        """Decide UPDATE-existing or CREATE-new for a new note, in one LLM shot."""
        candidates = self._candidates(f"{title}\n{body}")
        # Render full candidate bodies, the same content the loop's adjudicator
        # reads (index_text = description + body), so the comparison is symmetric.
        context_text = self._render_bodies(candidates)
        prompt = f"{self._guidance}\n\n{_ROUTE_INSTRUCTION}\n\nNew note '{title}':\n{body}"
        generation = self._generator.generate(prompt, context_text)
        return _parse_decision(generation.text, set(self._bundle.concepts))

    def _candidates(self, text: str) -> list[str]:
        return [neighbor.concept_id for neighbor in self._index.query_text(text, self._candidate_k)]

    def _render_bodies(self, concept_ids: list[str]) -> str:
        blocks: list[str] = []
        for concept_id in concept_ids:
            concept = self._bundle.concepts.get(concept_id)
            if concept is None:
                continue
            blocks.append(f"## {concept_id}\n{concept.body.strip()}")
        return "\n\n".join(blocks)


def _parse_cited(text: str, valid_ids: set[str]) -> list[str]:
    """Pull cited concept ids from the answer, keeping only ids that exist."""
    cited: list[str] = []
    match = _CITED.search(text)
    if match is not None:
        for token in re.split(r"[,\s]+", match.group("ids").strip()):
            candidate = token.strip().strip(".`")
            if candidate in valid_ids and candidate not in cited:
                cited.append(candidate)
    return cited


def _parse_decision(text: str, valid_ids: set[str]) -> PromptDecision:
    """Parse an 'UPDATE <id>' / 'CREATE' decision; default to CREATE if unclear."""
    update = _UPDATE.search(text)
    if update is not None:
        concept_id = update.group("id").strip().strip(".`")
        return PromptDecision("UPDATE", concept_id if concept_id in valid_ids else None)
    if _CREATE.search(text) is not None:
        return PromptDecision("CREATE", None)
    return PromptDecision("CREATE", None)
