"""Centralized, injectable path resolution for the private evidence vault.

Evidence never lives inside the OKF bundle or a repository-tracked directory
(DEVELOPMENT_PLAN.md M2; enhancement plan §9). The default root is
``~/.kosha/evidence/<bundle-identity>``, where ``<bundle-identity>`` is a
stable hash of the bundle's canonical path -- never the path itself, so a
vault directory listing does not disclose operator filesystem layout.

Every path derived from caller-controlled input (a digest, a run identifier)
is validated here before it is ever joined onto a filesystem path, so no
other module in ``kosha.evidence`` performs its own path arithmetic.
"""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Mapping
from pathlib import Path

_HOME_ENV_VAR = "KOSHA_HOME"
_DEFAULT_HOME_DIRNAME = ".kosha"
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


class InvalidDigestError(ValueError):
    """Raised when a value is not a validated lowercase 64-hex-char SHA-256 digest."""


class InvalidRunIdError(ValueError):
    """Raised when a run identifier is empty or would escape the vault root."""


def validate_digest(digest: str) -> str:
    """Return ``digest`` unchanged if it is a lowercase 64-hex-char SHA-256 digest."""
    if not _DIGEST_RE.fullmatch(digest):
        raise InvalidDigestError(f"not a validated lowercase SHA-256 digest: {digest!r}")
    return digest


def validate_run_id(run_id: str) -> str:
    """Return ``run_id`` unchanged if it is a safe single path segment."""
    if not run_id or "\x00" in run_id:
        raise InvalidRunIdError(f"invalid run_id: {run_id!r}")
    if run_id in {".", ".."} or Path(run_id).name != run_id:
        raise InvalidRunIdError(f"run_id must not contain path separators: {run_id!r}")
    return run_id


def kosha_home(env: Mapping[str, str] | None = None) -> Path:
    """Return the operator-private Kosha data root, honoring ``KOSHA_HOME``."""
    source = os.environ if env is None else env
    override = source.get(_HOME_ENV_VAR, "").strip()
    if override:
        return Path(override)
    return Path.home() / _DEFAULT_HOME_DIRNAME


def bundle_identity(bundle_path: Path) -> str:
    """Return a stable digest of ``bundle_path``'s canonical form, never the path itself."""
    canonical = str(Path(bundle_path).resolve())
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def evidence_root(
    bundle_path: Path,
    *,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    """Return the default private evidence root for the bundle at ``bundle_path``.

    ``home`` overrides the resolved Kosha data root directly (for tests);
    ``env`` is only consulted when ``home`` is omitted.
    """
    base = home if home is not None else kosha_home(env)
    return base / "evidence" / bundle_identity(bundle_path)


def object_path(root: Path, digest: str) -> Path:
    """Return the content-addressed object path for a validated ``digest`` under ``root``."""
    return root / "objects" / validate_digest(digest)


def manifest_path(root: Path, run_id: str) -> Path:
    """Return the source-run manifest path for ``run_id`` under ``root``."""
    return root / "runs" / f"{validate_run_id(run_id)}.json"
