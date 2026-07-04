"""Typed in-memory model of an OKF knowledge bundle.

These Pydantic models are the single typed boundary every later milestone reads
and writes through. They mirror the OKF v0.1 concept document (frontmatter +
body) and Kosha's internal provenance layer (claims), plus the typed shapes used
to regenerate ``index.md`` files.

Design constraints encoded here:

* ``Frontmatter`` requires ``type`` (OKF conformance rule 2) and tolerates
  arbitrary producer-defined keys (``extra="allow"``), so unknown keys survive a
  parse/serialize round-trip rather than being dropped.
* ``effective_from`` / ``effective_to`` / ``access_level`` are Kosha extensions
  the OKF spec tolerates as unknown keys; they are promoted to typed fields here
  because the maintenance loop reasons over them.
* The on-disk artifact stays plain OKF markdown. ``Claim`` is an internal
  provenance index used by the merge/writer milestone; it is not serialized as a
  separate structure.
* ``Source`` / ``RawDoc`` are the ingest-layer boundary: an adapter normalizes a
  URL or local Markdown file into a ``RawDoc`` (text + ``Source`` provenance),
  and the extractor reads ``RawDoc`` to propose concepts.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ClaimStatus(StrEnum):
    """Lifecycle state of a single claim within a concept."""

    CURRENT = "current"
    SUPERSEDED = "superseded"
    CONTRADICTED = "contradicted"


class SourceKind(StrEnum):
    """Origin kind of ingested material (system_design §8.1 build cut)."""

    URL = "url"
    MARKDOWN = "markdown"


class Frontmatter(BaseModel):
    """YAML frontmatter of a concept document.

    Only ``type`` is required by the OKF spec. Unknown keys are preserved
    (``extra="allow"``) so producer extensions survive round-trips.
    """

    model_config = ConfigDict(extra="allow")

    type: str
    title: str | None = None
    description: str | None = None
    resource: str | None = None
    tags: list[str] = Field(default_factory=list)
    timestamp: datetime | None = None
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    access_level: str | None = None


class Claim(BaseModel):
    """A provenance-bearing assertion that composes a concept body.

    The claim layer lets a merge supersede a specific statement instead of
    rewriting the whole body, which keeps fidelity stable across many ingests.
    ``supersedes`` chains a replacement claim back to the claim it retired, so a
    concept's full lineage (current head + retired ancestors) is reconstructable
    without deleting history.

    ``effective_from`` / ``effective_to`` carry per-claim temporal validity
    (``effective_to is None`` means currently in force). The contradiction
    resolution policy reads this window to supersede an expired claim by a
    later-effective one, retaining the old with its window closed (§3.2, §4.3.1).

    ``reviewer`` records the approving identity a claim was minted or superseded
    under, when known (set behind an explicit approval gate; ``None`` for a claim
    hydrated from a disk-loaded body with no attributable reviewer). ``contradicts``
    chains a ``contradicted`` claim back to the claim it lost against when the
    resolution policy did not already link the two via ``supersedes`` — the case
    where the incumbent claim stays current and the challenger is retained, not
    replaced (M7 claim lineage; system_design §4.3.1).
    """

    claim_id: str
    statement: str
    source_id: str
    asserted_at: datetime
    status: ClaimStatus = ClaimStatus.CURRENT
    citations: list[str] = Field(default_factory=list)
    supersedes: str | None = None
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    reviewer: str | None = None
    contradicts: str | None = None


class Concept(BaseModel):
    """A single unit of knowledge: one OKF markdown document."""

    concept_id: str
    frontmatter: Frontmatter
    body: str
    claims: list[Claim] = Field(default_factory=list)
    out_links: list[str] = Field(default_factory=list)


class IndexEntry(BaseModel):
    """One linked item in an ``index.md`` section."""

    title: str
    target: str
    description: str | None = None


class IndexSection(BaseModel):
    """A headed group of entries within an ``index.md`` body."""

    heading: str
    entries: list[IndexEntry] = Field(default_factory=list)


class IndexDoc(BaseModel):
    """The typed content of an ``index.md`` file.

    ``okf_version`` is set only for a bundle-root index, the sole place the spec
    allows index frontmatter.
    """

    sections: list[IndexSection] = Field(default_factory=list)
    okf_version: str | None = None


class Bundle(BaseModel):
    """A self-contained collection of concepts: the OKF unit of distribution."""

    root_path: str
    okf_version: str = "0.1"
    git_remote: str | None = None
    concepts: dict[str, Concept] = Field(default_factory=dict)


class Source(BaseModel):
    """Provenance of ingested material.

    ``authority_rank`` is the source-authority input the contradiction-resolution
    policy (M9) uses to break ties: higher wins. ``source_id`` is the stable
    provenance key stamped on every :class:`Claim` later derived from this source.
    """

    source_id: str
    kind: SourceKind
    location: str
    title: str | None = None
    authority_rank: int = 0
    retrieved_at: datetime | None = None


class RawDoc(BaseModel):
    """Normalized text pulled from a :class:`Source` — the deterministic ingest output.

    Ingest adapters realize ``fetch(source) -> RawDoc`` (system_design §2.2):
    they pull a URL or local Markdown file and normalize it to plain text plus
    source metadata. The concept extractor segments ``text`` into candidate
    concepts; nothing downstream re-fetches the original source.
    """

    source: Source
    text: str
