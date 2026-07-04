"""Bundle registry for served traversal surfaces.

The registry is the network-serving boundary's dispatch table. It holds loaded
``KoshaKnowledgeService`` instances, requires an explicit bundle identity for every
operation, and delegates each traversal call to exactly one bundle. It never offers
a cross-bundle search path.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypedDict, cast

from kosha.index.embedding import EmbeddingIndex
from kosha.mcp.service import AccessDeniedError, KoshaKnowledgeService
from kosha.okf.load import load_bundle
from kosha.providers import resolve_embedding_provider

ToolName = Literal[
    "claim_history",
    "find_concepts",
    "follow_links",
    "list_index",
    "load_concept",
    "read_frontmatter",
]
ToolArguments = Mapping[str, object]
ToolResult = Mapping[str, object]


class BundleInfo(TypedDict):
    """One bundle visible to the current served caller."""

    bundle_id: str


@dataclass(frozen=True)
class BundleRegistration:
    """One loaded service registered under a stable client-facing id."""

    bundle_id: str
    service: KoshaKnowledgeService

    def __post_init__(self) -> None:
        if not self.bundle_id.strip():
            raise ValueError("bundle_id must not be blank")
        if "/" in self.bundle_id or ".." in self.bundle_id:
            raise ValueError("bundle_id must be an opaque id, not a path")


class BundleRegistry:
    """Explicit-bundle dispatch over traversal-only services."""

    def __init__(self, registrations: Iterable[BundleRegistration]) -> None:
        services: dict[str, KoshaKnowledgeService] = {}
        for registration in registrations:
            if registration.bundle_id in services:
                raise ValueError(f"duplicate bundle_id {registration.bundle_id!r}")
            services[registration.bundle_id] = registration.service
        if not services:
            raise ValueError("at least one bundle registration is required")
        self._services = services

    def bundle_ids(self) -> list[str]:
        """Return every registered bundle id, regardless of caller clearance."""

        return sorted(self._services)

    def authorized_bundle_ids(self) -> list[str]:
        """Return bundle ids whose service accepts the current caller clearance."""

        visible: list[str] = []
        for bundle_id in self.bundle_ids():
            service = self._services[bundle_id]
            try:
                service.list_index("")
            except AccessDeniedError:
                continue
            visible.append(bundle_id)
        return visible

    def require_service(self, bundle_id: str) -> KoshaKnowledgeService:
        """Return the service for ``bundle_id`` or fail without path interpretation."""

        if not bundle_id:
            raise KeyError("bundle_id is required")
        try:
            return self._services[bundle_id]
        except KeyError as exc:
            raise KeyError(f"unknown bundle_id {bundle_id!r}") from exc

    def call_tool(
        self, bundle_id: str, tool_name: ToolName | str, arguments: ToolArguments
    ) -> ToolResult:
        """Dispatch one traversal call to exactly one addressed bundle."""

        service = self.require_service(bundle_id)
        if tool_name == "list_index":
            return cast(ToolResult, service.list_index(_optional_str(arguments, "scope", "")))
        if tool_name == "read_frontmatter":
            return cast(
                ToolResult,
                service.read_frontmatter(_required_str(arguments, "concept_id")),
            )
        if tool_name == "load_concept":
            return cast(
                ToolResult,
                service.load_concept(
                    _required_str(arguments, "concept_id"),
                    asof=_optional_nullable_str(arguments, "asof"),
                ),
            )
        if tool_name == "find_concepts":
            return cast(
                ToolResult,
                service.find_concepts(
                    _required_str(arguments, "query"),
                    _optional_int(arguments, "k", 3),
                ),
            )
        if tool_name == "follow_links":
            return cast(ToolResult, service.follow_links(_required_str(arguments, "concept_id")))
        if tool_name == "claim_history":
            return cast(
                ToolResult,
                service.claim_history(
                    _required_str(arguments, "concept_id"),
                    _optional_nullable_str(arguments, "claim_id"),
                ),
            )
        raise KeyError(f"unknown traversal tool {tool_name!r}")


def build_single_bundle_registry(
    bundle_path: Path,
    *,
    bundle_id: str = "default",
    bundle_access: str | None = None,
    clearance: Iterable[str] = (),
) -> BundleRegistry:
    """Load one bundle into a registry for served mode or tests."""

    bundle = load_bundle(bundle_path)
    index = EmbeddingIndex.build(bundle, resolve_embedding_provider())
    service = KoshaKnowledgeService(
        bundle,
        index,
        bundle_access=bundle_access,
        clearance=clearance,
    )
    return BundleRegistry([BundleRegistration(bundle_id=bundle_id, service=service)])


def build_bundles_dir_registry(
    bundles_dir: Path,
    *,
    access_by_bundle: Mapping[str, str] | None = None,
    clearance: Iterable[str] = (),
) -> BundleRegistry:
    """Load each direct child directory in ``bundles_dir`` as one bundle id."""

    access_by_bundle = access_by_bundle or {}
    children = sorted(path for path in bundles_dir.iterdir() if path.is_dir())
    child_ids = {child.name for child in children}
    unknown = sorted(set(access_by_bundle) - child_ids)
    if unknown:
        raise ValueError(
            "--bundle-access specified unknown bundle id(s): " + ", ".join(unknown)
        )
    registrations: list[BundleRegistration] = []
    for child in children:
        registrations.append(
            _load_registration(
                child,
                bundle_id=child.name,
                bundle_access=access_by_bundle.get(child.name),
                clearance=clearance,
            )
        )
    return BundleRegistry(registrations)


def _load_registration(
    bundle_path: Path,
    *,
    bundle_id: str,
    bundle_access: str | None,
    clearance: Iterable[str],
) -> BundleRegistration:
    bundle = load_bundle(bundle_path)
    index = EmbeddingIndex.build(bundle, resolve_embedding_provider())
    service = KoshaKnowledgeService(
        bundle,
        index,
        bundle_access=bundle_access,
        clearance=clearance,
    )
    return BundleRegistration(bundle_id=bundle_id, service=service)


def _required_str(arguments: ToolArguments, key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _optional_str(arguments: ToolArguments, key: str, default: str) -> str:
    value = arguments.get(key, default)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value


def _optional_nullable_str(arguments: ToolArguments, key: str) -> str | None:
    value = arguments.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string or null")
    return value


def _optional_int(arguments: ToolArguments, key: str, default: int) -> int:
    value = arguments.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{key} must be a positive integer")
    return value
