"""Source-instance configuration and durable connector cursor state.

An explicit, hand-registered connector registry wires existing ingest
adapters (``kosha.ingest.folder``/``kosha.ingest.url``) into repeatable,
operator-configured source instances whose mutable cursor state advances
only after a run's evidence has actually been persisted. See
DEVELOPMENT_PLAN.md M6 and ``.docs/memory-and-openwiki-enhancement-plan.md``
§13 for the governing contract. No dynamic plugin loader, interactive
config editor, or OAuth storage exists here or is planned for this
milestone -- see ``kosha.connectors.config`` for the registry.
"""

from __future__ import annotations

from kosha.connectors.config import (
    CONNECTOR_REGISTRY,
    SourceConfigError,
    UnknownConnectorError,
    load_source_instance,
    load_source_instances,
    resolve_connector,
)
from kosha.connectors.model import (
    ConnectorBackend,
    ConnectorDefinition,
    ConnectorRunContext,
    ConnectorState,
    RunSummary,
    SourceInstance,
    SourceRunOutcome,
)
from kosha.connectors.run import SourceRunReport, run_source_instance
from kosha.connectors.state import (
    ConnectorStateCorruptionError,
    ConnectorStateStore,
    connectors_root,
    instance_state_path,
)

__all__ = [
    "CONNECTOR_REGISTRY",
    "ConnectorBackend",
    "ConnectorDefinition",
    "ConnectorRunContext",
    "ConnectorState",
    "ConnectorStateCorruptionError",
    "ConnectorStateStore",
    "RunSummary",
    "SourceConfigError",
    "SourceInstance",
    "SourceRunOutcome",
    "SourceRunReport",
    "UnknownConnectorError",
    "connectors_root",
    "instance_state_path",
    "load_source_instance",
    "load_source_instances",
    "resolve_connector",
    "run_source_instance",
]
