"""Shared fixtures for the MCP consumer-surface tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from kosha.index.embedding import EmbeddingIndex
from kosha.mcp.service import KoshaKnowledgeService
from kosha.model import Bundle
from kosha.okf.load import load_bundle
from kosha.providers import LexicalEmbeddingProvider

NORTHWIND = Path(__file__).resolve().parents[2] / "bundles" / "northwind"


def make_service(bundle: Bundle) -> KoshaKnowledgeService:
    """Build a service over ``bundle`` with the deterministic local embedder."""
    index = EmbeddingIndex.build(bundle, LexicalEmbeddingProvider())
    return KoshaKnowledgeService(bundle, index)


@pytest.fixture
def northwind() -> Bundle:
    return load_bundle(NORTHWIND)


@pytest.fixture
def service(northwind: Bundle) -> KoshaKnowledgeService:
    return make_service(northwind)
