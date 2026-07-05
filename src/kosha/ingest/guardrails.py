"""Shared ingest adapter contract and guardrails.

Every source adapter normalizes untrusted bytes into :class:`kosha.model.RawDoc`.
This module keeps that boundary single-sourced: adapters declare stable
provenance, enforce a byte cap before constructing text, and strip hidden
prompt-injection obfuscation before downstream generation prompts see it.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from kosha.model import RawDoc, Source
from kosha.security.prompt_guard import sanitize_untrusted_text

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
