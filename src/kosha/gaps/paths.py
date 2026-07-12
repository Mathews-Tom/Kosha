"""Centralized, injectable path resolution for the private knowledge-gap ledger.

Mirrors :mod:`kosha.evidence.paths` / :mod:`kosha.connectors.state`: the gap
ledger never lives inside the OKF bundle or a repository-tracked directory,
rooted at ``~/.kosha/gaps/<bundle-identity>/`` by default and honoring
``KOSHA_HOME``.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from kosha.evidence.paths import bundle_identity, kosha_home

_LEDGER_FILENAME = "gaps.json"


def gaps_root(
    bundle_path: Path,
    *,
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    """Return the default private gap-ledger root for the bundle at ``bundle_path``.

    ``home`` overrides the resolved Kosha data root directly (for tests);
    ``env`` is only consulted when ``home`` is omitted.
    """
    base = home if home is not None else kosha_home(env)
    return base / "gaps" / bundle_identity(bundle_path)


def ledger_path(root: Path) -> Path:
    """Return the single ledger file path under a gap-ledger ``root``."""
    return root / _LEDGER_FILENAME
