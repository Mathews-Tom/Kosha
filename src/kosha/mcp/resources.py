"""``kosha://`` bundle resource URIs, ACL, and read functions (M9).

MCP clients read live bundle state (system_design §16) through versioned
resources layered over the same :class:`~kosha.server.registry.BundleRegistry`
the traversal tools already dispatch through -- no new read path, no raw-text
search. Four URI shapes exist:

.. code-block:: text

    kosha://bundles
    kosha://bundles/{bundle_id}
    kosha://bundles/{bundle_id}/index/{scope}
    kosha://bundles/{bundle_id}/concepts/{concept_id}

``bundle_id``, ``scope``, and ``concept_id`` are opaque path segments:
:func:`encode_segment`/:func:`decode_segment` percent-encode/decode each one so
a scope containing ``/`` (a nested directory) or any other reserved character
round-trips as exactly one URI path segment, matching the FastMCP resource
template matcher's one-segment-per-``{param}`` regex. The bundle-root scope
(``""``) has no resource form -- read it through the ``list_index`` tool
instead; every resource segment here is required to be non-empty.

ACL runs **before** existence disclosure (source spec §16): :func:`require_authorized_bundle`
raises the same :class:`ResourceAccessError`, with the same generic message,
whether ``bundle_id`` does not exist or exists but is outside the server
process's configured clearance. A caller can never use a resource read (or,
per :mod:`kosha.mcp.subscriptions`, a subscription) to distinguish "no such
bundle" from "bundle exists, access denied." This module owns that check
once; :mod:`kosha.mcp.server` and :mod:`kosha.mcp.subscriptions` both call it
rather than re-deriving bundle visibility.

This module never imports the ``mcp`` SDK (mirrors :mod:`kosha.mcp.service`):
only :mod:`kosha.mcp.server` and :mod:`kosha.mcp.subscriptions`, which wire
these functions into FastMCP, require the optional dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict
from urllib.parse import quote, unquote

from kosha.mcp.service import (
    ClaimHistoryView,
    ConceptView,
    FindView,
    FrontmatterView,
    IndexView,
    LinksView,
)
from kosha.server.registry import BundleRegistry, BundleRevisionView

SCHEME_PREFIX = "kosha://"
BUNDLES_LIST_URI = "kosha://bundles"
BUNDLE_URI_TEMPLATE = "kosha://bundles/{bundle_id}"
INDEX_URI_TEMPLATE = "kosha://bundles/{bundle_id}/index/{scope}"
CONCEPT_URI_TEMPLATE = "kosha://bundles/{bundle_id}/concepts/{concept_id}"

RESOURCE_MIME_TYPE = "application/json"


class MalformedResourceUriError(ValueError):
    """Raised when a string is not a recognized ``kosha://`` resource URI shape."""


class ResourceAccessError(PermissionError):
    """Raised for a bundle-scoped resource whose id is unknown or unauthorized.

    Deliberately carries no bundle-specific detail in its message: a resource
    read (or subscribe) cannot be used as an oracle to enumerate bundle ids
    the caller's clearance does not cover.
    """

    def __init__(self) -> None:
        super().__init__("bundle not found or access denied")


class BundleListView(TypedDict):
    """``kosha://bundles``' content: every authorized bundle's id and revision."""

    bundles: list[BundleRevisionView]


class RevisionedIndexView(IndexView):
    revision: str


class RevisionedFrontmatterView(FrontmatterView):
    revision: str


class RevisionedConceptView(ConceptView):
    revision: str


class RevisionedFindView(FindView):
    revision: str


class RevisionedLinksView(LinksView):
    revision: str


class RevisionedClaimHistoryView(ClaimHistoryView):
    revision: str


@dataclass(frozen=True)
class BundlesListRef:
    """A parsed reference to ``kosha://bundles``."""


@dataclass(frozen=True)
class BundleRef:
    """A parsed reference to ``kosha://bundles/{bundle_id}``."""

    bundle_id: str


@dataclass(frozen=True)
class IndexRef:
    """A parsed reference to ``kosha://bundles/{bundle_id}/index/{scope}``."""

    bundle_id: str
    scope: str


@dataclass(frozen=True)
class ConceptRef:
    """A parsed reference to ``kosha://bundles/{bundle_id}/concepts/{concept_id}``."""

    bundle_id: str
    concept_id: str


ResourceRef = BundlesListRef | BundleRef | IndexRef | ConceptRef


def encode_segment(value: str) -> str:
    """Percent-encode one opaque path segment (``bundle_id``/``scope``/``concept_id``)."""

    if not value:
        raise ValueError("resource URI segment must not be empty")
    return quote(value, safe="")


def decode_segment(segment: str) -> str:
    """Percent-decode one path segment, rejecting an empty (root-scope) result."""

    value = unquote(segment)
    if not value:
        raise MalformedResourceUriError("resource URI segment must not be empty")
    return value


def bundles_list_uri() -> str:
    return BUNDLES_LIST_URI


def bundle_uri(bundle_id: str) -> str:
    return f"kosha://bundles/{encode_segment(bundle_id)}"


def index_uri(bundle_id: str, scope: str) -> str:
    return f"kosha://bundles/{encode_segment(bundle_id)}/index/{encode_segment(scope)}"


def concept_uri(bundle_id: str, concept_id: str) -> str:
    return f"kosha://bundles/{encode_segment(bundle_id)}/concepts/{encode_segment(concept_id)}"


def parse_resource_uri(uri: str) -> ResourceRef:
    """Parse and validate a ``kosha://`` resource URI into its typed shape.

    Raises :class:`MalformedResourceUriError` for anything else, including a
    non-``kosha://`` scheme, an unrecognized path shape, and an empty
    ``bundle_id``/``scope``/``concept_id`` segment.
    """

    if not uri.startswith(SCHEME_PREFIX):
        raise MalformedResourceUriError(f"not a kosha:// resource URI: {uri!r}")
    rest = uri[len(SCHEME_PREFIX) :]
    segments = rest.split("/") if rest else [""]
    if any(not segment for segment in segments):
        raise MalformedResourceUriError(f"malformed kosha:// resource URI: {uri!r}")
    if segments == ["bundles"]:
        return BundlesListRef()
    if len(segments) == 2 and segments[0] == "bundles":
        return BundleRef(bundle_id=decode_segment(segments[1]))
    if len(segments) == 4 and segments[0] == "bundles" and segments[2] == "index":
        return IndexRef(bundle_id=decode_segment(segments[1]), scope=decode_segment(segments[3]))
    if len(segments) == 4 and segments[0] == "bundles" and segments[2] == "concepts":
        return ConceptRef(
            bundle_id=decode_segment(segments[1]), concept_id=decode_segment(segments[3])
        )
    raise MalformedResourceUriError(f"unrecognized kosha:// resource URI shape: {uri!r}")


def require_authorized_bundle(registry: BundleRegistry, bundle_id: str) -> None:
    """Raise :class:`ResourceAccessError` unless ``bundle_id`` is currently authorized.

    The single ACL gate every resource (and subscription) read runs before
    touching any bundle-specific state, so "unknown bundle" and "known
    bundle, access denied" are indistinguishable to the caller.
    """

    if bundle_id not in registry.authorized_bundle_ids():
        raise ResourceAccessError


def read_bundles_list(registry: BundleRegistry) -> BundleListView:
    """Return ``kosha://bundles``' content: every authorized bundle, with revision."""

    return {"bundles": registry.authorized_bundle_revisions()}


def read_bundle(registry: BundleRegistry, bundle_id: str) -> BundleRevisionView:
    """Return ``kosha://bundles/{bundle_id}``'s content: id and active revision."""

    require_authorized_bundle(registry, bundle_id)
    registration = registry.active_registration(bundle_id)
    return {"bundle_id": bundle_id, "revision": registration.revision}


def read_index(registry: BundleRegistry, bundle_id: str, scope: str) -> RevisionedIndexView:
    """Return ``kosha://bundles/{bundle_id}/index/{scope}``'s content."""

    require_authorized_bundle(registry, bundle_id)
    result = registry.call_tool(bundle_id, "list_index", {"scope": scope})
    return dict(result)  # type: ignore[return-value]


def read_concept(
    registry: BundleRegistry, bundle_id: str, concept_id: str
) -> RevisionedConceptView:
    """Return ``kosha://bundles/{bundle_id}/concepts/{concept_id}``'s content.

    Applies the same temporal claim filtering as the ``load_concept`` tool's
    default (``asof=None``): only claims currently in force render.
    """

    require_authorized_bundle(registry, bundle_id)
    result = registry.call_tool(
        bundle_id, "load_concept", {"concept_id": concept_id, "asof": None}
    )
    return dict(result)  # type: ignore[return-value]
