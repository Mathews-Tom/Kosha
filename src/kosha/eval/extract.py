"""Score the concept extractor's boundary quality against seed granularity labels.

The granularity seed labels each class a document as ``atomic`` (one concept) or
``overscoped`` (many concepts bundled together). The extractor is run over each
label's text and graded on whether its draft count matches that class:

* an ``atomic`` doc must yield exactly one draft (it did not over-split), and
* an ``overscoped`` doc must yield more than one (it caught the over-scoping).

This discriminates against both failure modes the plan flags for the extractor:
a whole-document extractor (one draft always) fails every overscoped case, and
an over-splitter (e.g. one draft per sentence) fails the multi-sentence atomic
cases. Concepts in the seed are heading-delimited, so the score measures
heading-boundary recovery; decoupling heading count from concept count is future
label-set work, with the M6 dedup ``split`` branch as the runtime safety net. The
score is the fraction of labels the extractor classifies correctly.
"""

from __future__ import annotations

from dataclasses import dataclass

from kosha.bench import GranularityLabel
from kosha.extract import extract_concepts
from kosha.model import RawDoc, Source, SourceKind
from kosha.providers.base import GenerationProvider
from kosha.telemetry import TelemetrySink, emit_provider_call

_ATOMIC = "atomic"


@dataclass(frozen=True)
class ExtractEvalCase:
    """The graded outcome for one granularity label."""

    label: str
    expected_atomic: bool
    draft_count: int
    correct: bool


@dataclass(frozen=True)
class ExtractEvalReport:
    """The extractor eval outcome over the whole label set."""

    label_count: int
    correct: int
    cases: tuple[ExtractEvalCase, ...]

    @property
    def score(self) -> float:
        """Fraction of labels whose boundary class the extractor recovered."""
        return self.correct / self.label_count if self.label_count else 1.0


def evaluate_extractor(
    labels: list[GranularityLabel],
    provider: GenerationProvider,
    *,
    telemetry_sink: TelemetrySink | None = None,
) -> ExtractEvalReport:
    """Grade the extractor's boundary calls against the granularity labels."""
    if not labels:
        raise ValueError("no granularity labels to evaluate")
    cases: list[ExtractEvalCase] = []
    correct = 0
    for label in labels:
        emit_provider_call(
            telemetry_sink,
            surface="eval.extract",
            provider_name=provider.name,
        )
        count = len(extract_concepts(_raw_from_text(label.text), provider))
        expected_atomic = label.label == _ATOMIC
        ok = count == 1 if expected_atomic else count > 1
        correct += int(ok)
        cases.append(
            ExtractEvalCase(
                label=label.label,
                expected_atomic=expected_atomic,
                draft_count=count,
                correct=ok,
            )
        )
    return ExtractEvalReport(label_count=len(labels), correct=correct, cases=tuple(cases))


def _raw_from_text(text: str) -> RawDoc:
    source = Source(
        source_id="eval://granularity",
        kind=SourceKind.MARKDOWN,
        location="eval://granularity",
    )
    return RawDoc(source=source, text=text)
