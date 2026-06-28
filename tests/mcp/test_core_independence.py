"""The pure consumer surface loads without the optional ``mcp`` SDK.

A fresh interpreter proves ``import kosha.mcp`` (the traversal service + the
non-MCP fallback) pulls neither the ``mcp`` dependency nor the FastMCP server
module, so the producer loop and the fallback path stay free of the optional
extra (system_design §6 fallbacks; "minimal deps").
"""

from __future__ import annotations

import subprocess
import sys


def test_pure_surface_does_not_import_mcp_sdk() -> None:
    code = (
        "import sys, kosha, kosha.mcp; "
        "assert 'mcp' not in sys.modules; "
        "assert 'kosha.mcp.server' not in sys.modules; "
        "from kosha.mcp import KoshaKnowledgeService, render_fallback_fragment; "
        "print('ok')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"
