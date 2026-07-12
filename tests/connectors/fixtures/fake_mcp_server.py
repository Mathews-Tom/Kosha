"""A tiny, deterministic, local MCP server used only by the MCP connector tests.

Runs over stdio via ``FastMCP`` and exposes a fixed set of tools exercising
every branch of the connector's allowlist/annotation/schema-pin/destructive
authorization matrix: a read-only tool, an unannotated tool (safe only
behind an operator-pinned schema hash), a destructive tool that must always
be rejected, a slow tool for timeout coverage, an oversized-output tool for
response-cap coverage, and an env-probe tool that proves which environment
variables the connector actually forwarded into this subprocess.
"""

from __future__ import annotations

import os
import time

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

app = FastMCP("fake-source")


@app.tool(annotations=ToolAnnotations(readOnlyHint=True))
def list_items() -> str:
    """Return a small, fixed list of items."""
    return "item-1\nitem-2\nitem-3"


@app.tool(annotations=ToolAnnotations(readOnlyHint=True))
def echo_args(value: str) -> str:
    """Echo back the given value."""
    return f"echo:{value}"


@app.tool()
def unannotated_read() -> str:
    """A tool that declares no annotations at all (safe only via a pinned schema hash)."""
    return "unannotated payload"


@app.tool(annotations=ToolAnnotations(destructiveHint=True))
def delete_everything() -> str:
    """A destructive tool that must always be rejected, allowlisted or not."""
    return "deleted"


@app.tool(annotations=ToolAnnotations(readOnlyHint=True))
def slow_tool() -> str:
    """A read-only tool that sleeps well past any reasonable connector timeout."""
    time.sleep(5)
    return "slow"


@app.tool(annotations=ToolAnnotations(readOnlyHint=True))
def big_tool() -> str:
    """A read-only tool whose output exceeds any reasonable response cap."""
    return "x" * 1_000_000


@app.tool(annotations=ToolAnnotations(readOnlyHint=True))
def env_probe(var_name: str) -> str:
    """Report whether ``var_name`` is present in this subprocess's environment."""
    return f"value={os.environ.get(var_name, '<unset>')}"


if __name__ == "__main__":
    app.run(transport="stdio")
