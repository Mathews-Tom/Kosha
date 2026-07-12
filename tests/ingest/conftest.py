"""Shared fixtures for tests/ingest.

Deterministic ingest tests must never silently pick up a workstation-exported
remote generation/embedding provider (M1). ``resolve_generation_provider`` and
``resolve_embedding_provider`` default to ``os.environ`` when a pipeline call
site does not inject a provider explicitly, so an ambient ``KOSHA_GEN_*`` /
``KOSHA_EMBED_*`` value would otherwise make these tests attempt a real network
call. Provider-resolution precedence itself is untouched -- this only clears
the ambient variables the deterministic tests in this directory never intend
to exercise; tests that specifically assert environment precedence (e.g.
``tests/providers/test_factory.py``) always pass an explicit env mapping and
are unaffected by this fixture.
"""

from __future__ import annotations

import pytest

_AMBIENT_PROVIDER_VARS = (
    "KOSHA_GEN_BASE_URL",
    "KOSHA_GEN_MODEL",
    "KOSHA_GEN_API_KEY",
    "KOSHA_EMBED_BASE_URL",
    "KOSHA_EMBED_MODEL",
    "KOSHA_EMBED_API_KEY",
    "KOSHA_EMBED_DIM",
)


@pytest.fixture(autouse=True)
def _clear_ambient_provider_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear remote-provider selection variables before every ingest test."""
    for var in _AMBIENT_PROVIDER_VARS:
        monkeypatch.delenv(var, raising=False)
