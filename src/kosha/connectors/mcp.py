"""Allowlisted, read-only MCP source connector (DEVELOPMENT_PLAN.md M7).

Calls exactly one operator-configured tool on one operator-configured MCP
server over stdio, and stages its (capped, text-only) response as ordinary
evidence through the shared connector run boundary
(:mod:`kosha.connectors.run`). Tool names and descriptions from the server
are untrusted (enhancement plan §14): they never authorize a call by
themselves. A call is authorized only when

    the tool is in the instance's explicit ``allowed_tools`` list
    AND (the tool declares ``readOnlyHint=true``
         OR the operator has pinned this tool's exact current schema hash
            in ``pinned_schema_hashes``)

and a tool the server marks ``destructiveHint=true`` is rejected
unconditionally, regardless of allowlist or pin. The live schema is fetched
fresh every run -- never trusted from a prior run or cached -- so a server
that changes a pinned tool's schema between runs (``pinned_schema_hashes``
no longer matching) stops the run rather than silently re-authorizing it.

Kosha itself never resolves or stores a credential for the target server:
the subprocess inherits only the SDK's own safe default environment plus
the specific variable *names* this instance's ``forwarded_env_vars`` names
(never their values, matching the "config stores names, never values"
convention every other connector config field already follows) -- any
credential the target server needs is the operator's own subprocess
environment concern, identical to a Claude Desktop-style MCP client config.

Importing this module never requires the optional ``mcp``/``anyio``
dependencies (``kosha-okf[mcp]``); only calling :func:`run_mcp_source` does,
mirroring :mod:`kosha.mcp.server`'s own optional-dependency boundary.
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from kosha.connectors.model import ConnectorRunContext, SourceInstance
from kosha.evidence import CoverageKind, SourceCoverage
from kosha.ingest.guardrails import build_raw_doc
from kosha.model import Source, SourceKind
from kosha.pipeline import IngestResult, ingest

_DEFAULT_TIMEOUT_SECONDS = 10
_DEFAULT_MAX_OUTPUT_BYTES = 200_000


class McpConnectorError(ValueError):
    """Raised when an MCP source instance's config is invalid or malformed."""


class McpAuthorizationError(McpConnectorError):
    """Raised when a tool call is not authorized under the allow/annotation/pin rule."""


class McpTransportError(McpConnectorError):
    """Raised when the transport fails, times out, or the server reports a tool error."""


def hash_tool_schema(schema: Mapping[str, object]) -> str:
    """Return the deterministic SHA-256 hash of a tool's JSON input schema.

    An operator computes this once (from the reviewed schema they intend to
    pin) with the exact same function the connector uses at run time, so a
    pinned value in config is directly comparable to what a live run
    observes.
    """
    return _canonical_hash(schema)


def hash_arguments(arguments: Mapping[str, object]) -> str:
    """Return the deterministic SHA-256 hash of one tool call's argument object."""
    return _canonical_hash(arguments)


def _canonical_hash(obj: object) -> str:
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class _McpInstanceConfig:
    server_name: str
    command: str
    args: tuple[str, ...]
    tool_name: str
    allowed_tools: frozenset[str]
    pinned_schema_hashes: Mapping[str, str]
    forwarded_env: Mapping[str, str]
    timeout_seconds: int
    max_output_bytes: int
    arguments: Mapping[str, object]
    authority: int


@dataclass(frozen=True)
class _McpCallOutcome:
    text: str
    schema_hash: str
    argument_hash: str


def _unwrap_single(exc: BaseException) -> BaseException:
    """Recursively unwrap a single-exception ``BaseExceptionGroup`` to its leaf."""
    while isinstance(exc, BaseExceptionGroup) and len(exc.exceptions) == 1:
        exc = exc.exceptions[0]
    return exc

def run_mcp_source(ctx: ConnectorRunContext) -> IngestResult:
    """Wire the allowlisted, read-only MCP connector through ``ingest()``.

    Fails loud -- and never calls ``ingest()`` at all, so no evidence is
    ever bound or persisted -- for an unlisted tool, a tool the live server
    does not advertise, a destructive tool, a tool that is neither
    read-only nor correctly pinned, an oversized response, a timeout, or
    any other transport failure.
    """
    import anyio  # deferred: kept out of this module's import-time surface

    config = _parse_config(ctx.instance)
    if config.tool_name not in config.allowed_tools:
        raise McpAuthorizationError(
            f"tool {config.tool_name!r} is not in this instance's allowlist "
            f"{sorted(config.allowed_tools)}"
        )
    try:
        outcome = anyio.run(_call_tool, config)
    except BaseExceptionGroup as group:
        # `stdio_client`/`ClientSession` tear their internal task groups down
        # through the exception that propagates out of `_call_tool`'s `with`
        # block, wrapping it in one (or, nested, two) single-exception
        # `BaseExceptionGroup`s. Unwrap back to the connector's own raised
        # error so callers (and `run_source_instance`'s FAILED-run message)
        # see it directly instead of an opaque task-group wrapper.
        raise _unwrap_single(group) from group

    text = (
        f"MCP source: {config.server_name}\n"
        f"Transport: stdio command={config.command} args={' '.join(config.args)}\n"
        f"Tool: {config.tool_name}\n"
        f"Schema SHA-256: {outcome.schema_hash}\n"
        f"Argument SHA-256: {outcome.argument_hash}\n\n"
        f"{outcome.text}\n"
    )
    source = Source(
        source_id=f"mcp/{ctx.instance.instance_id}.md",
        kind=SourceKind.MCP,
        location=f"{config.server_name}::{config.tool_name}",
        title=f"{config.server_name}: {config.tool_name}",
        authority_rank=config.authority,
        retrieved_at=ctx.asof,
    )
    raw = build_raw_doc(source=source, text=text)
    coverage = SourceCoverage(
        kind=CoverageKind.BEST_EFFORT,
        scope=f"MCP tool call {config.tool_name!r} on server {config.server_name!r}",
    )
    return ingest(
        Path("mcp-source") / ctx.instance.instance_id,
        ctx.bundle_root,
        asof=ctx.asof,
        source_authority=config.authority,
        dry_run=ctx.dry_run,
        assume_yes=ctx.assume_yes,
        reader=ctx.reader,
        reviewer=ctx.reviewer,
        raw_docs=[raw],
        evidence_store=ctx.evidence_store,
        coverage=coverage,
    )


async def _call_tool(config: _McpInstanceConfig) -> _McpCallOutcome:
    import anyio
    from mcp.client.stdio import StdioServerParameters, stdio_client

    from mcp import ClientSession

    with anyio.fail_after(config.timeout_seconds):
        params = StdioServerParameters(
            command=config.command, args=list(config.args), env=dict(config.forwarded_env)
        )
        async with stdio_client(params) as (read_stream, write_stream), ClientSession(
            read_stream, write_stream
        ) as session:
            await session.initialize()
            listing = await session.list_tools()
            tool = next((t for t in listing.tools if t.name == config.tool_name), None)
            if tool is None:
                raise McpAuthorizationError(
                    f"server {config.server_name!r} does not currently advertise tool "
                    f"{config.tool_name!r}"
                )
            schema_hash = hash_tool_schema(tool.inputSchema)
            annotations = tool.annotations
            if annotations is not None and annotations.destructiveHint:
                raise McpAuthorizationError(
                    f"tool {config.tool_name!r} declares destructiveHint=true; rejected"
                )
            read_only = annotations is not None and annotations.readOnlyHint is True
            pinned = config.pinned_schema_hashes.get(config.tool_name)
            if not read_only and pinned != schema_hash:
                if pinned is None:
                    raise McpAuthorizationError(
                        f"tool {config.tool_name!r} does not declare readOnlyHint=true and no "
                        "operator-pinned schema hash is configured for it"
                    )
                raise McpAuthorizationError(
                    f"tool {config.tool_name!r}'s live schema hash {schema_hash} does not "
                    f"match the operator-pinned hash {pinned}; its schema has drifted"
                )
            argument_hash = hash_arguments(config.arguments)
            result = await session.call_tool(config.tool_name, dict(config.arguments))
            if result.isError:
                raise McpTransportError(f"tool {config.tool_name!r} reported an error result")
            text = _extract_and_cap_text(result.content, max_bytes=config.max_output_bytes)
    return _McpCallOutcome(text=text, schema_hash=schema_hash, argument_hash=argument_hash)


def _extract_and_cap_text(content: Sequence[object], *, max_bytes: int) -> str:
    """Concatenate every text content block; fail loud before returning any text if oversized."""
    chunks: list[str] = []
    total = 0
    for block in content:
        text = getattr(block, "text", None)
        if not isinstance(text, str):
            continue
        total += len(text.encode("utf-8"))
        if total > max_bytes:
            raise McpTransportError(f"tool response exceeded max_output_bytes={max_bytes}")
        chunks.append(text)
    return "\n".join(chunks)


def _parse_config(instance: SourceInstance) -> _McpInstanceConfig:
    config = instance.config
    server_name = config.get("server_name") or instance.instance_id
    command = config["command"]
    args = tuple(shlex.split(config.get("args", "")))
    tool_name = config["tool_name"]
    allowed_tools = frozenset(
        name.strip() for name in config.get("allowed_tools", "").split(",") if name.strip()
    )
    pinned_schema_hashes = _json_str_mapping(
        config.get("pinned_schema_hashes", "{}"), field="pinned_schema_hashes"
    )
    forwarded_names = [
        name.strip() for name in config.get("forwarded_env_vars", "").split(",") if name.strip()
    ]
    forwarded_env = _resolve_forwarded_env(forwarded_names)
    timeout_seconds = _positive_int(
        config.get("timeout_seconds", str(_DEFAULT_TIMEOUT_SECONDS)), field="timeout_seconds"
    )
    max_output_bytes = _positive_int(
        config.get("max_output_bytes", str(_DEFAULT_MAX_OUTPUT_BYTES)), field="max_output_bytes"
    )
    arguments = _json_object(config.get("arguments", "{}"), field="arguments")
    authority = int(config.get("authority", "0"))
    return _McpInstanceConfig(
        server_name=server_name,
        command=command,
        args=args,
        tool_name=tool_name,
        allowed_tools=allowed_tools,
        pinned_schema_hashes=pinned_schema_hashes,
        forwarded_env=forwarded_env,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
        arguments=arguments,
        authority=authority,
    )


def _resolve_forwarded_env(names: list[str]) -> Mapping[str, str]:
    """Resolve each declared env-var *name* from Kosha's own environment.

    Fails loud when a declared name is absent -- silently omitting it would
    let the subprocess start without a credential the operator explicitly
    said it needs, surfacing as a confusing downstream transport failure
    instead of a clear one here.
    """
    resolved: dict[str, str] = {}
    for name in names:
        if name not in os.environ:
            raise McpConnectorError(
                f"forwarded_env_vars names {name!r}, which is not set in this environment"
            )
        resolved[name] = os.environ[name]
    return resolved


def _json_object(raw: str, *, field: str) -> Mapping[str, object]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise McpConnectorError(f"{field} must be a JSON object, got {raw!r}: {exc}") from exc
    if not isinstance(value, dict):
        raise McpConnectorError(f"{field} must be a JSON object, got {raw!r}")
    return value


def _json_str_mapping(raw: str, *, field: str) -> Mapping[str, str]:
    value = _json_object(raw, field=field)
    if not all(isinstance(v, str) for v in value.values()):
        raise McpConnectorError(f"{field} must be a JSON object of string values, got {raw!r}")
    return {str(key): str(entry) for key, entry in value.items()}


def _positive_int(raw: str, *, field: str) -> int:
    try:
        value = int(raw)
    except ValueError:
        raise McpConnectorError(f"{field} must be an integer, got {raw!r}") from None
    if value < 1:
        raise McpConnectorError(f"{field} must be positive, got {value}")
    return value
