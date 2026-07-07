"""Check MCP and fallback traversal public surfaces against live sources."""

from __future__ import annotations

import ast
import importlib.util
from dataclasses import dataclass
from pathlib import Path

from kosha.mcp.fallback import render_consumer_skill, render_fallback_fragment
from kosha.sync.check import SyncMismatch
from kosha.sync.writer import GeneratedSectionWriter

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

    spec = importlib.util.find_spec("kosha.mcp.server")
    if spec is None or spec.origin is None:
        raise RuntimeError("cannot locate kosha.mcp.server source")
    source_path = Path(spec.origin)
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
    docstring = ast.get_docstring(node)
    description = (
        docstring.splitlines()[0].rstrip(".") if docstring else "No description"
    )
    return McpTool(
        name=node.name,
        signature=_signature(node.args),
        description=description,
    )


def _signature(args: ast.arguments) -> str:
    defaults = [None] * (len(args.args) - len(args.defaults)) + list(args.defaults)
    rendered = [
        _argument_signature(arg, default)
        for arg, default in zip(args.args, defaults, strict=True)
    ]
    kw_defaults = [
        _argument_signature(arg, default)
        for arg, default in zip(args.kwonlyargs, args.kw_defaults, strict=True)
    ]
    if kw_defaults:
        rendered.append("*")
        rendered.extend(kw_defaults)
    if args.vararg is not None:
        rendered.append("*" + _argument_signature(args.vararg, None))
    if args.kwarg is not None:
        rendered.append("**" + _argument_signature(args.kwarg, None))
    return "(" + ", ".join(rendered) + ")"


def _argument_signature(arg: ast.arg, default: ast.expr | None) -> str:
    annotation = (
        f": {ast.unparse(arg.annotation)}" if arg.annotation is not None else ""
    )
    default_value = f" = {ast.unparse(default)}" if default is not None else ""
    return f"{arg.arg}{annotation}{default_value}"


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
    return SyncMismatch(
        surface=surface, path=path, message="expected traversal surface is missing"
    )


def write_mcp_integration_doc(repo_root: Path) -> None:
    path = repo_root / MCP_DOC_PATH
    if not path.is_file():
        return
        
    text = path.read_text(encoding="utf-8")
    writer = GeneratedSectionWriter("mcp-tool-table")
    
    rows = render_mcp_tool_rows()
    lines = [
        "| Tool | Signature | Returns |",
        "|---|---|---|",
        *rows
    ]
    
    new_text = writer.write_section(text, "\n".join(lines))
    path.write_text(new_text, encoding="utf-8")

def write_fallback_artifacts(repo_root: Path) -> None:
    expected = {
        FALLBACK_FRAGMENT_PATH: render_fallback_fragment(),
        FALLBACK_SKILL_PATH: render_consumer_skill(),
    }
    for relative, rendered in expected.items():
        path = repo_root / relative
        if not path.parent.is_dir():
            path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")
