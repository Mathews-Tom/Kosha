"""Versioned bundle releases: tag and export a validated snapshot (M8 PR-5).

A release is a promise: the tagged ref was OKF-conformant when cut, and the
tag never moves once created. :func:`create_release` enforces both — it
refuses a bundle with conformance errors, and refuses to re-tag a version that
already exists (unlike the ingest pipeline's force-moving daily
``backup/<date>`` tag). Since the tag simply names an existing commit and the
optional export is a pure function of that commit's tree, cutting the same
release twice (distinct tag names) from unchanged content is reproducible:
the exported archives are byte-identical.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from kosha.git_store import GitStore
from kosha.okf import load_bundle
from kosha.validate import validate_bundle

_RELEASE_PREFIX = "release"


class ReleaseError(RuntimeError):
    """A release precondition failed: conformance errors or a duplicate tag."""


@dataclass(frozen=True)
class ReleaseRecord:
    """The outcome of tagging (and optionally exporting) a validated release."""

    tag: str
    ref: str
    timestamp: str
    concept_count: int
    warning_count: int
    export_path: str | None = None


def release_tag_name(version: str) -> str:
    """Return the immutable tag name for a release ``version`` (``v1`` -> ``release/v1``)."""
    return f"{_RELEASE_PREFIX}/{version}"


def create_release(
    store: GitStore,
    bundle_root: Path,
    version: str,
    *,
    asof: datetime | None = None,
    export_path: Path | None = None,
) -> ReleaseRecord:
    """Validate ``bundle_root``'s current state and tag it as an immutable release.

    Validates the on-disk bundle at HEAD — the ordinary "release what I just
    committed" workflow — not an arbitrary historical ref, so the preflight
    always reflects exactly what the new tag will point to.

    Raises :class:`ReleaseError` when the bundle has conformance errors or
    ``version``'s tag already exists; raises :class:`~kosha.git_store.GitError`
    on any other Git failure (e.g. an unsupported ``export_path`` suffix).
    """
    asof = asof or datetime.now(UTC)
    report = validate_bundle(bundle_root)
    if report.errors:
        raise ReleaseError(
            f"bundle is not OKF-conformant ({len(report.errors)} error(s)); refusing to release"
        )
    tag = release_tag_name(version)
    if store.tag_exists(tag):
        raise ReleaseError(f"release tag already exists: {tag} (releases are immutable)")
    ref = store.current_sha("HEAD")
    store.create_tag(tag, ref)
    exported: str | None = None
    if export_path is not None:
        store.export_archive(tag, export_path)
        exported = str(export_path)
    concept_count = len(load_bundle(bundle_root).concepts)
    return ReleaseRecord(
        tag=tag,
        ref=ref,
        timestamp=asof.isoformat(),
        concept_count=concept_count,
        warning_count=len(report.warnings),
        export_path=exported,
    )
