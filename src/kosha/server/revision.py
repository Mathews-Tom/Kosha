"""Bundle revision identity and atomic activation state for live serving (M8).

A *revision* is a deterministic content hash of a bundle directory: the same
formula :mod:`kosha.sync.snapshot` already uses for generated-surface
freshness checks, reused here rather than inventing a second hash convention
(source spec §15 "Revision contract"). An :class:`ActiveRegistration` is the
complete, immutable (bundle, index, service) triple currently being served
for one bundle id; :class:`~kosha.server.registry.BundleRegistry` swaps one
whole registration into place per activation, so a reader always observes
either the complete previous registration or the complete new one, never a
partially replaced pair.

:class:`RefreshError` and :class:`ActivationEvent` are deliberately narrow --
a stage/message/timestamp and a bundle_id/revision/timestamp, respectively --
so neither a failed-refresh report nor an activation notification can ever
carry source or concept body text.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from kosha.sync.snapshot import content_snapshot

if TYPE_CHECKING:
    from kosha.mcp.service import KoshaKnowledgeService

RevisionHealth = Literal["current", "stale", "failed"]

_GIT_HEAD_TIMEOUT_SECONDS = 5


def default_clock() -> datetime:
    """The registry's default activation clock: real wall-clock UTC time."""

    return datetime.now(UTC)


def compute_bundle_revision(bundle_root: Path) -> str:
    """Return the deterministic content revision for a bundle directory.

    Every file's exact bytes under ``bundle_root``, hashed in stable sorted
    order and rolled into one SHA-256 digest -- meaningful bundle content only,
    excluding nothing serving-specific because a bundle directory holds no
    volatile serving metadata of its own.
    """

    return content_snapshot(bundle_root).sha256


def resolve_source_git_head(bundle_root: Path) -> str | None:
    """Return ``git rev-parse HEAD`` for ``bundle_root``, or ``None`` when unavailable.

    Best-effort provenance only (source spec: "source Git HEAD when
    available") -- a bundle directory outside any Git work tree, or a missing
    ``git`` binary, is not a failure; it just means this field is absent.
    """

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=bundle_root,
            capture_output=True,
            text=True,
            timeout=_GIT_HEAD_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    head = result.stdout.strip()
    return head or None


@dataclass(frozen=True)
class RefreshError:
    """Source-free metadata about one failed refresh attempt.

    ``message`` is always built from a fixed template plus an exception type
    name or a finding count -- never the raw exception text -- so a parser or
    validator error can never leak a fragment of bundle content here.
    """

    stage: Literal["revision", "load", "validate", "index"]
    message: str
    occurred_at: str


@dataclass(frozen=True)
class ActiveRegistration:
    """One bundle's complete, currently-served (bundle, index, service) triple."""

    bundle_id: str
    service: KoshaKnowledgeService
    revision: str
    activated_at: str
    source_git_head: str | None


@dataclass(frozen=True)
class ActivationEvent:
    """One completed activation: bundle id and revision only, never body text."""

    bundle_id: str
    revision: str
    activated_at: str


@dataclass(frozen=True)
class RefreshOutcome:
    """The result of one :meth:`BundleRegistry.refresh` call."""

    bundle_id: str
    changed: bool
    revision: str
    health: RevisionHealth
    error: RefreshError | None = None
