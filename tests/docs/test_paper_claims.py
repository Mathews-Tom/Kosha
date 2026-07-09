from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / ".docs" / "s2-v3-preregistration.md"

def test_preregistration_document_exists() -> None:
    assert PREREG.exists()

def test_preregistration_covers_required_scope() -> None:
    text = PREREG.read_text("utf-8")
    assert "criteria" in text.lower()
    assert "provider matrix shape" in text.lower()
    assert "case counts" in text.lower()
    assert "go/no-go semantics" in text.lower()
    assert "local-smoke" in text.lower()
