"""Shared fixtures for the whole test suite.

An ``ingest()``/``commit_plan()`` call that receives no explicit
``evidence_store`` resolves the default private evidence vault under
``KOSHA_HOME`` (DEVELOPMENT_PLAN.md M2/M3: ``evidence_root`` defaults to
``~/.kosha/evidence/<bundle-identity>`` when ``KOSHA_HOME`` is unset).
Redirecting that here, once, for every test -- rather than requiring every
call site across the suite to inject an explicit store -- is what keeps a
full test run from ever touching the operator's real ``~/.kosha`` vault. A
test that specifically exercises evidence durability still injects its own
:class:`~kosha.evidence.EvidenceStore` under ``tmp_path`` and is unaffected
by this environment redirect either way.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_kosha_home(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Point the default evidence vault root at a private per-test directory."""
    home = tmp_path_factory.mktemp("kosha-home")
    monkeypatch.setenv("KOSHA_HOME", str(home))
