"""Check MCP and fallback traversal public surfaces against live sources."""

from __future__ import annotations

import ast
import inspect
from dataclasses import dataclass
from pathlib import Path

from kosha.mcp.fallback import render_consumer_skill, render_fallback_fragment
from kosha.sync.check import SyncMismatch

MCP_DOC_PATH = Path("docs/mcp-integration.md")
FALLBACK_FRAGMENT_PATH = Path("consumer/AGENTS.fragment.md")
FALLBACK_SKILL_PATH = Path("consumer/kosha-traversal/SKILL.md")


@dataclass(frozen=True)
class McpTool:
    """One FastMCP tool registered by ``kosha.mcp.server``."""

    name: str
    signature: str
    description: str


def check_traversal_surfaces(repo_root: Path) -> tuple[SyncMismatch, ...]:
    """Return mismatches for MCP docs and fallback traversal artifacts."""

    mismatches: list[SyncMismatch] = []
    mismatches.extend(check_mcp_integration_doc(repo_root))
    mismatches.extend(check_fallback_artifacts(repo_root))
    return tuple(mismatches)


def check_mcp_integration_doc(repo_root: Path) -> tuple[SyncMismatch, ...]:
    """Check that MCP docs list the live registry-server tool signatures."""

    path = repo_root / MCP_DOC_PATH
    if not path.is_file():
        return (_missing_file("mcp-integration", path),)
    text = path.read_text(encoding="utf-8")
    missing = tuple(row for row in render_mcp_tool_rows() if row not in text)
    if not missing:
        return ()
    return (
        SyncMismatch(
            surface="mcp-integration",
            path=path,
            message="MCP integration tool table does not match live server tools",
            details=tuple(f"missing row: {row}" for row in missing),
        ),
    )


def check_fallback_artifacts(repo_root: Path) -> tuple[SyncMismatch, ...]:
    """Check committed non-MCP fallback files against ``kosha.mcp.fallback``."""

    expected = {
        FALLBACK_FRAGMENT_PATH: render_fallback_fragment(),
        FALLBACK_SKILL_PATH: render_consumer_skill(),
    }
    mismatches: list[SyncMismatch] = []
    for relative, rendered in expected.items():
        path = repo_root / relative
        if not path.is_file():
            mismatches.append(_missing_file("fallback-artifact", path))
            continue
        actual = path.read_text(encoding="utf-8")
        if actual != rendered:
            mismatches.append(
                SyncMismatch(
                    surface="fallback-artifact",
                    path=path,
                    message="fallback artifact does not match kosha.mcp.fallback output",
                    details=("expected bytes from kosha.mcp.fallback",),
                )
            )
    return tuple(mismatches)


def live_mcp_tools() -> tuple[McpTool, ...]:
    """Return the FastMCP registry-server tools parsed from the server source."""

    from kosha.mcp import server as mcp_server

    source_path = Path(inspect.getsourcefile(mcp_server) or "")
    if not source_path.is_file():
        raise RuntimeError("cannot locate kosha.mcp.server source")
    module = ast.parse(source_path.read_text(encoding="utf-8"))
    builder = _find_function(module, "_build_registry_server")
    tools = [
        node
        for node in builder.body
        if isinstance(node, ast.FunctionDef) and _is_tool(node)
    ]
    return tuple(_tool_from_function(node) for node in tools)


def render_mcp_tool_rows() -> tuple[str, ...]:
    """Render docs table rows for the live registry-server tool surface."""

    return tuple(
        f"| `{tool.name}` | `{_escape_table_cell(tool.signature)}` | {tool.description} |"
        for tool in live_mcp_tools()
    )


def _tool_from_function(node: ast.FunctionDef) -> McpTool:
    return McpTool(
        name=node.name,
        signature=_signature(node.args),
        description=(ast.get_docstring(node) or "").splitlines()[0].rstrip("."),
    )


def _signature(args: ast.arguments) -> str:
    defaults = [None] * (len(args.args) - len(args.defaults)) + list(args.defaults)
    rendered: list[str] = []
    for arg, default in zip(args.args, defaults, strict=True):
        annotation = f": {ast.unparse(arg.annotation)}" if arg.annotation is not None else ""
        default_value = f" = {ast.unparse(default)}" if default is not None else ""
        rendered.append(f"{arg.arg}{annotation}{default_value}")
    return "(" + ", ".join(rendered) + ")"


def _escape_table_cell(value: str) -> str:
    return value.replace("|", r"\|")


def _find_function(module: ast.Module, name: str) -> ast.FunctionDef:
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise RuntimeError(f"cannot find {name} in kosha.mcp.server")


def _is_tool(node: ast.FunctionDef) -> bool:
    return any(
        isinstance(decorator, ast.Call)
        and isinstance(decorator.func, ast.Attribute)
        and decorator.func.attr == "tool"
        for decorator in node.decorator_list
    )


def _missing_file(surface: str, path: Path) -> SyncMismatch:
    return SyncMismatch(surface=surface, path=path, message="expected traversal surface is missing")
