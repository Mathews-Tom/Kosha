"""Explicit shipped-connector registry and source-instance config loading.

No dynamic plugin loader: connectors are a fixed, hand-maintained mapping
from ``connector_id`` to a :class:`~kosha.connectors.model.ConnectorDefinition`.
``folder``/``url`` wire an existing ``kosha.ingest`` adapter through the
ordinary plan -> approve -> commit gate (``kosha.pipeline.run.ingest``) --
the same two adapters ``kosha.ingest.watch.ScheduledIngest`` already drives
(DEVELOPMENT_PLAN.md M6). ``git`` wires the bounded, read-only repository
connector in :mod:`kosha.connectors.git` (DEVELOPMENT_PLAN.md M7).
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

import pydantic

from kosha.connectors.git import run_git_source
from kosha.connectors.model import (
    ConnectorBackend,
    ConnectorDefinition,
    ConnectorRunContext,
    SourceInstance,
)
from kosha.evidence import CoverageKind, SourceCoverage
from kosha.ingest.guardrails import DEFAULT_MAX_BYTES
from kosha.ingest.url import fetch_url
from kosha.pipeline import IngestResult, ingest


class UnknownConnectorError(ValueError):
    """Raised when a source instance names a ``connector_id`` outside the shipped registry."""


class SourceConfigError(ValueError):
    """Raised when a source-instance config file or entry is missing, malformed, or invalid."""


def _run_folder(ctx: ConnectorRunContext) -> IngestResult:
    """Wire the existing local-folder adapter (``kosha.ingest.folder``) through ``ingest()``."""
    source_dir = ctx.instance.config["path"]
    authority = int(ctx.instance.config.get("authority", "0"))
    return ingest(
        Path(source_dir),
        ctx.bundle_root,
        asof=ctx.asof,
        source_authority=authority,
        dry_run=ctx.dry_run,
        assume_yes=ctx.assume_yes,
        reader=ctx.reader,
        reviewer=ctx.reviewer,
        evidence_store=ctx.evidence_store,
    )


def _run_url(ctx: ConnectorRunContext) -> IngestResult:
    """Wire the existing URL adapter (``kosha.ingest.url.fetch_url``) through ``ingest()``.

    Mirrors ``kosha.ingest.watch.ScheduledIngest.run_once``'s URL branch:
    fetch once, then pass the already-fetched ``RawDoc`` in as ``raw_docs``
    with an explicit complete-coverage-of-the-response-body statement.
    """
    url = ctx.instance.config["url"]
    authority = int(ctx.instance.config.get("authority", "0"))
    max_bytes = int(ctx.instance.config.get("max_bytes", str(DEFAULT_MAX_BYTES)))
    raw = fetch_url(url, authority_rank=authority, max_bytes=max_bytes)
    return ingest(
        Path(urlsplit(url).hostname or "url"),
        ctx.bundle_root,
        asof=ctx.asof,
        source_authority=authority,
        dry_run=ctx.dry_run,
        assume_yes=ctx.assume_yes,
        reader=ctx.reader,
        reviewer=ctx.reviewer,
        raw_docs=[raw],
        evidence_store=ctx.evidence_store,
        coverage=SourceCoverage(
            kind=CoverageKind.COMPLETE, scope=f"HTTP response body for {url}"
        ),
    )


FOLDER_CONNECTOR = ConnectorDefinition(
    connector_id="folder",
    display_name="Local Markdown folder",
    backend=ConnectorBackend.FOLDER,
    ingest=_run_folder,
    required_config_keys=("path",),
)

URL_CONNECTOR = ConnectorDefinition(
    connector_id="url",
    display_name="HTTP(S) page fetch",
    backend=ConnectorBackend.URL,
    ingest=_run_url,
    required_config_keys=("url",),
)

GIT_CONNECTOR = ConnectorDefinition(
    connector_id="git",
    display_name="Bounded Git repository history",
    backend=ConnectorBackend.GIT,
    ingest=run_git_source,
    required_config_keys=("path",),
    required_env_vars=("KOSHA_GIT_ALLOWED_ROOTS",),
    supports_cursor=True,
)

CONNECTOR_REGISTRY: dict[str, ConnectorDefinition] = {
    connector.connector_id: connector
    for connector in (FOLDER_CONNECTOR, URL_CONNECTOR, GIT_CONNECTOR)
}


def resolve_connector(connector_id: str) -> ConnectorDefinition:
    """Return the shipped ``ConnectorDefinition`` for ``connector_id``, failing loud if unknown."""
    try:
        return CONNECTOR_REGISTRY[connector_id]
    except KeyError:
        raise UnknownConnectorError(
            f"unknown connector_id {connector_id!r}; shipped connectors: "
            f"{sorted(CONNECTOR_REGISTRY)}"
        ) from None


def load_source_instances(path: Path) -> tuple[SourceInstance, ...]:
    """Load and validate every source instance from one JSON config file.

    The file is a JSON array of instance objects. Fails loud -- never falls
    back to an empty list -- on a missing file, malformed JSON, a non-array
    payload, an instance naming an unknown ``connector_id``, an instance
    missing a required config key for its connector, or a duplicate
    ``instance_id``.
    """
    if not path.is_file():
        raise SourceConfigError(f"no source-instance config file at {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceConfigError(f"malformed source-instance config at {path}: {exc}") from exc
    if not isinstance(raw, list):
        raise SourceConfigError(f"source-instance config at {path} must be a JSON array")
    instances: list[SourceInstance] = []
    seen: set[str] = set()
    for entry in raw:
        try:
            instance = SourceInstance.model_validate(entry)
        except (TypeError, pydantic.ValidationError) as exc:
            raise SourceConfigError(f"invalid source instance in {path}: {exc}") from exc
        if instance.instance_id in seen:
            raise SourceConfigError(f"duplicate instance_id {instance.instance_id!r} in {path}")
        seen.add(instance.instance_id)
        definition = resolve_connector(instance.connector_id)
        missing = [key for key in definition.required_config_keys if key not in instance.config]
        if missing:
            raise SourceConfigError(
                f"source instance {instance.instance_id!r} is missing required config "
                f"key(s) {missing} for connector {instance.connector_id!r}"
            )
        instances.append(instance)
    return tuple(instances)


def load_source_instance(path: Path, instance_id: str) -> SourceInstance:
    """Load one named instance from ``path``, failing loud if it is not configured."""
    for instance in load_source_instances(path):
        if instance.instance_id == instance_id:
            return instance
    raise SourceConfigError(f"no source instance {instance_id!r} configured in {path}")
