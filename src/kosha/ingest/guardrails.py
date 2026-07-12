"""Shared ingest adapter contract and guardrails.

Every source adapter normalizes untrusted bytes into :class:`kosha.model.RawDoc`.
This module keeps that boundary single-sourced: adapters declare stable
provenance, enforce a byte cap before constructing text, and strip hidden
prompt-injection obfuscation before downstream generation prompts see it.

:func:`bind_evidence` extends that single boundary with the shared evidence
identity every adapter's documents cross before extraction: an early secret
scan, a content-addressed digest, and a :class:`~kosha.evidence.SourceRun`
skeleton for the attempt (DEVELOPMENT_PLAN.md M3; enhancement plan §10).
Whether that identity ever becomes durable is decided later, by
:func:`persist_evidence_run`, and only for an approved, non-dry-run commit.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from kosha.evidence import EvidenceDocument, RunStatus, SourceRun, hash_evidence_text
from kosha.evidence.store import EvidenceStore
from kosha.model import RawDoc, Source
from kosha.security.prompt_guard import sanitize_untrusted_text
from kosha.security.secret_scan import scan_text

DEFAULT_MAX_BYTES = 10 * 1024 * 1024
_READ_CHUNK_BYTES = 65536


class IngestGuardrailError(ValueError):
    """Raised when source content violates a shared ingest guardrail."""


@dataclass(frozen=True)
class IngestPolicy:
    """Fail-closed policy shared by local and remote ingest adapters."""

    max_bytes: int = DEFAULT_MAX_BYTES
    sanitize_prompt_injection: bool = True

    def __post_init__(self) -> None:
        if self.max_bytes < 1:
            raise ValueError("max_bytes must be positive")


DEFAULT_INGEST_POLICY = IngestPolicy()


class IngestAdapter(Protocol):
    """Adapter contract: normalize a local source into guarded RawDoc objects."""

    def __call__(
        self,
        source: Path,
        *,
        authority_rank: int = 0,
        policy: IngestPolicy = DEFAULT_INGEST_POLICY,
    ) -> list[RawDoc]: ...


def read_text_file_bounded(
    path: Path,
    *,
    policy: IngestPolicy = DEFAULT_INGEST_POLICY,
    encoding: str = "utf-8",
) -> str:
    """Read a text file under ``policy.max_bytes``, failing loud on oversize."""

    data = read_bytes_bounded(path, policy=policy)
    return data.decode(encoding)


def read_bytes_bounded(path: Path, *, policy: IngestPolicy = DEFAULT_INGEST_POLICY) -> bytes:
    """Read at most ``policy.max_bytes`` bytes from ``path`` without truncating."""

    chunks: list[bytes] = []
    total = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(_READ_CHUNK_BYTES)
            if not chunk:
                return b"".join(chunks)
            total += len(chunk)
            if total > policy.max_bytes:
                raise IngestGuardrailError(
                    f"source file {path} exceeded max_bytes={policy.max_bytes}"
                )
            chunks.append(chunk)


def guard_text(
    text: str,
    *,
    source_location: str,
    policy: IngestPolicy = DEFAULT_INGEST_POLICY,
) -> str:
    """Apply shared text guardrails before a RawDoc crosses the ingest boundary."""

    if len(text.encode("utf-8")) > policy.max_bytes:
        raise IngestGuardrailError(
            f"source {source_location!r} exceeded max_bytes={policy.max_bytes}"
        )
    return sanitize_untrusted_text(text) if policy.sanitize_prompt_injection else text


def build_raw_doc(
    *,
    source: Source,
    text: str,
    policy: IngestPolicy = DEFAULT_INGEST_POLICY,
) -> RawDoc:
    """Construct a RawDoc only after shared guardrails have run."""

    return RawDoc(
        source=source,
        text=guard_text(text, source_location=source.location, policy=policy),
    )


def normalize_markdown(text: str) -> str:
    """Collapse intra-line whitespace and drop blank lines, keeping headings."""

    lines = (" ".join(line.split()) for line in text.splitlines())
    return "\n".join(line for line in lines if line)


def docs_from_paths(
    paths: Iterable[Path],
    *,
    source_for: Callable[[Path], Source],
    policy: IngestPolicy = DEFAULT_INGEST_POLICY,
) -> list[RawDoc]:
    """Build RawDocs from sorted paths through one guarded code path."""

    docs: list[RawDoc] = []
    for path in paths:
        text = read_text_file_bounded(path, policy=policy)
        docs.append(build_raw_doc(source=source_for(path), text=text, policy=policy))
    return docs


# --- evidence boundary ------------------------------------------------------
#
# Every adapter's RawDocs converge on `ingest()` (kosha.pipeline.run), whether
# built there directly (the folder adapter) or fetched by the caller and
# passed in as `raw_docs` (URL, workspace, document adapters). Binding
# evidence identity here -- once, over that already-converged list -- is what
# gives every adapter shape the same evidence boundary without touching each
# adapter module individually.

# The evidence store persists the exact normalized text every adapter already
# produces; every accepted document is described the same way regardless of
# its original remote media type.
_EVIDENCE_MEDIA_TYPE = "text/plain"
# Bumped only if the normalization pipeline `bind_evidence` hashes changes in
# a way that would make an old digest unverifiable against freshly read text.
EVIDENCE_NORMALIZATION_VERSION = "1"
# Placeholder pending M6 source-instance identity: one stable id per attempt,
# derived from the source the caller is ingesting.
_ADAPTER_VERSION = "1"


@dataclass(frozen=True)
class EvidenceRun:
    """The evidence identity computed for one ingest attempt, before commit.

    ``run`` is the immutable manifest skeleton (digests and metadata only);
    ``texts`` maps each digest to its exact normalized text, kept only in
    memory until an approved, non-dry-run commit persists it durably via
    :func:`persist_evidence_run`. Never put ``texts`` on a durable artifact
    directly -- only the store's content-addressed objects are the source of
    truth for evidence bytes.
    """

    run: SourceRun
    texts: Mapping[str, str]


def bind_evidence(
    docs: Sequence[RawDoc],
    *,
    run_id: str,
    bundle_identity: str,
    source_instance_id: str,
    started_at: datetime,
    completed_at: datetime,
) -> tuple[list[RawDoc], EvidenceRun | None]:
    """Scan and stamp evidence identity onto ``docs`` before extraction.

    Runs the early secret scan on each already-guarded document's exact text
    (DEVELOPMENT_PLAN.md M3 step 2, before the existing final-plan scan that
    remains a second line of defense). A document that matches contributes
    only its detector names to the run and its evidence: no evidence object
    is written for it and no claim later minted from it can carry evidence
    identity. It still reaches extraction unstamped (``source_run_id`` /
    ``evidence_sha256`` stay ``None``) so the existing final-plan scan --
    which inspects the *rendered concept*, not the raw source -- keeps
    working as the second line of defense the plan requires: a secret that
    survives into a change still forces that change's own BLOCK routing.

    Every other document is stamped with ``run_id`` and its content digest (a
    pure hash -- no filesystem write happens here). Returns ``(docs, None)``
    when ``docs`` is empty: there is no attempt to describe.
    """
    if not docs:
        return list(docs), None
    bound: list[RawDoc] = []
    documents: list[EvidenceDocument] = []
    texts: dict[str, str] = {}
    detector_names: set[str] = set()
    for raw in docs:
        detectors = scan_text(raw.text)
        if detectors:
            detector_names.update(detectors)
            bound.append(raw)
            continue
        digest = hash_evidence_text(raw.text)
        documents.append(
            EvidenceDocument(
                sha256=digest,
                source_id=raw.source.source_id,
                location=raw.source.location,
                retrieved_at=raw.source.retrieved_at,
                media_type=_EVIDENCE_MEDIA_TYPE,
                normalized_text_bytes=len(raw.text.encode("utf-8")),
                normalization_version=EVIDENCE_NORMALIZATION_VERSION,
            )
        )
        texts[digest] = raw.text
        bound.append(
            raw.model_copy(update={"source_run_id": run_id, "evidence_sha256": digest})
        )
    adapter = docs[0].source.kind.value
    status = RunStatus.ACCEPTED if documents else RunStatus.REJECTED
    run = SourceRun(
        run_id=run_id,
        bundle_identity=bundle_identity,
        source_instance_id=source_instance_id,
        adapter=adapter,
        adapter_version=_ADAPTER_VERSION,
        started_at=started_at,
        completed_at=completed_at,
        status=status,
        evidence=tuple(documents),
        detector_names=tuple(sorted(detector_names)),
    )
    return bound, EvidenceRun(run=run, texts=texts)


def persist_evidence_run(store: EvidenceStore, evidence_run: EvidenceRun) -> None:
    """Durably write ``evidence_run``'s objects, then its manifest.

    Only call this for an approved, non-dry-run commit (DEVELOPMENT_PLAN.md
    M3; enhancement plan §9 dry-run assumption) -- a dry run or a plan a
    reviewer ultimately rejects must leave no durable accepted object or
    manifest, so :func:`kosha.pipeline.run.commit_plan` is the only caller.
    Objects are written before the manifest (M2 ordering): an interrupted
    write leaves at most orphaned objects, never a manifest referencing one
    that is missing. A rejected run (no accepted documents) is not persisted
    here -- it carries no evidence to begin with, so there is nothing this
    function is responsible for making durable.
    """
    if evidence_run.run.status is not RunStatus.ACCEPTED:
        return
    for document in evidence_run.run.evidence:
        store.put_object(evidence_run.texts[document.sha256])
    store.write_run(evidence_run.run)
