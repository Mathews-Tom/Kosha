"""Bundle registry for served traversal surfaces.

The registry is the network-serving boundary's dispatch table. It holds one
:class:`~kosha.server.revision.ActiveRegistration` per bundle id, requires an
explicit bundle identity for every operation, and delegates each traversal
call to exactly one bundle. It never offers a cross-bundle search path.

Each registration tracks a deterministic content revision, a health status,
and the most recent refresh failure (if any) -- the model M8 live serving
activates atomically against (see :mod:`kosha.server.revision`). Every
traversal response and the bundle listing carry the serving revision that
answered them.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, TypedDict, cast

from kosha.index.embedding import EmbeddingIndex
from kosha.mcp.service import AccessDeniedError, KoshaKnowledgeService
from kosha.okf.load import load_bundle
from kosha.providers import resolve_embedding_provider
from kosha.server.revision import (
    ActivationEvent,
    ActiveRegistration,
    RefreshError,
    RevisionHealth,
    compute_bundle_revision,
    default_clock,
    resolve_source_git_head,
)

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


class BundleRevisionView(TypedDict):
    """One bundle's id and currently active revision, for an authorized caller."""

    bundle_id: str
    revision: str


class RefreshErrorView(TypedDict):
    """The reporting-safe (source-free) shape of a :class:`RefreshError`."""

    stage: str
    message: str
    occurred_at: str


class BundleHealthView(TypedDict):
    """One bundle's revision-aware serving state, for a health surface."""

    bundle_id: str
    revision: str
    health: RevisionHealth
    activated_at: str
    source_git_head: str | None
    last_error: RefreshErrorView | None


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
    """Explicit-bundle dispatch over traversal-only services, revision-tracked."""

    def __init__(
        self,
        registrations: Iterable[BundleRegistration],
        *,
        clock: Callable[[], datetime] = default_clock,
    ) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        active: dict[str, ActiveRegistration] = {}
        for registration in registrations:
            if registration.bundle_id in active:
                raise ValueError(f"duplicate bundle_id {registration.bundle_id!r}")
            active[registration.bundle_id] = _activate(
                registration.bundle_id, registration.service, clock
            )
        if not active:
            raise ValueError("at least one bundle registration is required")
        self._active = active
        self._health: dict[str, RevisionHealth] = dict.fromkeys(active, "current")
        self._errors: dict[str, RefreshError | None] = dict.fromkeys(active, None)
        self._activation_events: list[ActivationEvent] = []

    def bundle_ids(self) -> list[str]:
        """Return every registered bundle id, regardless of caller clearance."""

        return sorted(self._active)

    def authorized_bundle_ids(self) -> list[str]:
        """Return bundle ids whose service accepts the current caller clearance."""

        visible: list[str] = []
        for bundle_id in self.bundle_ids():
            service = self._active[bundle_id].service
            try:
                service.list_index("")
            except AccessDeniedError:
                continue
            visible.append(bundle_id)
        return visible

    def authorized_bundle_revisions(self) -> list[BundleRevisionView]:
        """Return id + active revision for every bundle the caller may see."""

        return [
            {"bundle_id": bundle_id, "revision": self._active[bundle_id].revision}
            for bundle_id in self.authorized_bundle_ids()
        ]

    def require_service(self, bundle_id: str) -> KoshaKnowledgeService:
        """Return the service for ``bundle_id`` or fail without path interpretation."""

        return self.active_registration(bundle_id).service

    def active_registration(self, bundle_id: str) -> ActiveRegistration:
        """Return the currently active, validated registration for ``bundle_id``."""

        if not bundle_id:
            raise KeyError("bundle_id is required")
        active = self._active  # snapshot the reference once; swaps replace it wholesale
        try:
            return active[bundle_id]
        except KeyError as exc:
            raise KeyError(f"unknown bundle_id {bundle_id!r}") from exc

    def health(self, bundle_id: str) -> RevisionHealth:
        """Return the health recorded by the most recent refresh attempt (no live check)."""

        self.active_registration(bundle_id)  # validates bundle_id, fails loud
        return self._health[bundle_id]

    def last_error(self, bundle_id: str) -> RefreshError | None:
        """Return the most recent refresh failure for ``bundle_id``, if any."""

        self.active_registration(bundle_id)
        return self._errors[bundle_id]

    def activation_events(self, bundle_id: str | None = None) -> tuple[ActivationEvent, ...]:
        """Return the activation history, optionally filtered to one bundle id."""

        if bundle_id is None:
            return tuple(self._activation_events)
        return tuple(event for event in self._activation_events if event.bundle_id == bundle_id)

    def health_view(self, bundle_id: str) -> BundleHealthView:
        """Return the reporting-safe health snapshot for ``bundle_id``.

        ``health`` here is a *live* check: a previously failed refresh attempt
        always reports ``"failed"``; otherwise the bundle's current on-disk
        revision is recomputed and compared against the active one, so a
        source change that has not yet been refreshed reports ``"stale"``
        rather than falsely claiming ``"current"``.
        """

        registration = self.active_registration(bundle_id)
        return {
            "bundle_id": bundle_id,
            "revision": registration.revision,
            "health": self._live_health(bundle_id, registration),
            "activated_at": registration.activated_at,
            "source_git_head": registration.source_git_head,
            "last_error": _error_view(self._errors[bundle_id]),
        }

    def _live_health(self, bundle_id: str, registration: ActiveRegistration) -> RevisionHealth:
        if self._health[bundle_id] == "failed":
            return "failed"
        try:
            root = Path(registration.service.bundle.root_path)
            current_source_revision = compute_bundle_revision(root)
        except Exception:
            return "stale"
        return "current" if current_source_revision == registration.revision else "stale"

    def call_tool(
        self, bundle_id: str, tool_name: ToolName | str, arguments: ToolArguments
    ) -> ToolResult:
        """Dispatch one traversal call to exactly one addressed bundle.

        The active registration is snapshotted once up front, so the
        ``revision`` merged into the response always matches the exact
        service instance that answered -- even if a concurrent refresh
        activates a newer revision while this call is still in flight.
        """

        registration = self.active_registration(bundle_id)
        result = _dispatch(registration.service, tool_name, arguments)
        return {**dict(result), "revision": registration.revision}


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


def _activate(
    bundle_id: str, service: KoshaKnowledgeService, clock: Callable[[], datetime]
) -> ActiveRegistration:
    root = Path(service.bundle.root_path)
    return ActiveRegistration(
        bundle_id=bundle_id,
        service=service,
        revision=compute_bundle_revision(root),
        activated_at=clock().isoformat(),
        source_git_head=resolve_source_git_head(root),
    )


def _error_view(error: RefreshError | None) -> RefreshErrorView | None:
    if error is None:
        return None
    return {"stage": error.stage, "message": error.message, "occurred_at": error.occurred_at}


def _dispatch(
    service: KoshaKnowledgeService, tool_name: ToolName | str, arguments: ToolArguments
) -> ToolResult:
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
