"""Multi-bundle registry: explicit-bundle dispatch, no cross-bundle leakage (M9 PR-2).

``BundleRegistry`` is the network-serving dispatch table: it holds several
loaded ``KoshaKnowledgeService`` instances and requires an explicit
``bundle_id`` for every call. These tests defend that every dispatch is
addressed to exactly one bundle, that a bundle's own clearance still applies
through the registry, and that the embedding jump (``find_concepts``) never
returns a candidate that lives in a different bundle.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from kosha.mcp.service import AccessDeniedError, KoshaKnowledgeService
from kosha.model import Bundle
from kosha.server.registry import (
    BundleRegistration,
    BundleRegistry,
    build_bundles_dir_registry,
)

ServiceFactory = Callable[..., KoshaKnowledgeService]


def _registry(
    build_service: ServiceFactory, northwind: Bundle, good_bundle: Bundle
) -> BundleRegistry:
    return BundleRegistry(
        [
            BundleRegistration("northwind", build_service(northwind)),
            BundleRegistration("good", build_service(good_bundle)),
            BundleRegistration(
                "locked", build_service(northwind, bundle_access="confidential")
            ),
        ]
    )


def test_bundle_ids_lists_every_registration_regardless_of_clearance(
    build_service: ServiceFactory, northwind: Bundle, good_bundle: Bundle
) -> None:
    registry = _registry(build_service, northwind, good_bundle)
    assert registry.bundle_ids() == ["good", "locked", "northwind"]


def test_authorized_bundle_ids_excludes_a_bundle_without_clearance(
    build_service: ServiceFactory, northwind: Bundle, good_bundle: Bundle
) -> None:
    registry = _registry(build_service, northwind, good_bundle)
    assert registry.authorized_bundle_ids() == ["good", "northwind"]


def test_call_tool_routes_to_the_addressed_bundles_own_service(
    build_service: ServiceFactory, northwind: Bundle, good_bundle: Bundle
) -> None:
    registry = _registry(build_service, northwind, good_bundle)
    result = registry.call_tool(
        "good", "read_frontmatter", {"concept_id": "concepts/customer-lifetime-value"}
    )
    assert result["title"] == "Customer Lifetime Value"


def test_call_tool_denies_a_bundle_the_service_lacks_clearance_for(
    build_service: ServiceFactory, northwind: Bundle, good_bundle: Bundle
) -> None:
    registry = _registry(build_service, northwind, good_bundle)
    with pytest.raises(AccessDeniedError):
        registry.call_tool("locked", "list_index", {})


def test_call_tool_on_an_unknown_bundle_id_fails_loud(
    build_service: ServiceFactory, northwind: Bundle, good_bundle: Bundle
) -> None:
    registry = _registry(build_service, northwind, good_bundle)
    with pytest.raises(KeyError, match="unknown bundle_id"):
        registry.call_tool("does-not-exist", "list_index", {})


@pytest.mark.parametrize("blank_bundle_id", ["", None])
def test_call_tool_never_falls_back_to_the_registrys_only_bundle(
    build_service: ServiceFactory, northwind: Bundle, blank_bundle_id: str | None
) -> None:
    # A registry with a single bundle must still refuse a missing/blank
    # bundle_id rather than silently treating "the only bundle" as an
    # implicit default -- every call must be explicitly addressed.
    single = BundleRegistry([BundleRegistration("northwind", build_service(northwind))])
    with pytest.raises(KeyError):
        single.call_tool(blank_bundle_id, "list_index", {})  # type: ignore[arg-type]


def test_call_tool_rejects_an_unknown_tool_name(
    build_service: ServiceFactory, northwind: Bundle, good_bundle: Bundle
) -> None:
    registry = _registry(build_service, northwind, good_bundle)
    with pytest.raises(KeyError, match="unknown traversal tool"):
        registry.call_tool("northwind", "delete_bundle", {})


def test_find_concepts_returns_candidates_only_from_the_addressed_bundle(
    build_service: ServiceFactory, northwind: Bundle, good_bundle: Bundle
) -> None:
    registry = _registry(build_service, northwind, good_bundle)
    result = registry.call_tool(
        "good", "find_concepts", {"query": "customer lifetime value", "k": 5}
    )
    ids = {candidate["concept_id"] for candidate in result["candidates"]}
    assert ids  # the good bundle's own concept was found
    assert ids <= set(good_bundle.concepts)  # never a northwind concept id


def test_find_concepts_on_a_different_bundle_never_returns_the_other_bundles_concepts(
    build_service: ServiceFactory, northwind: Bundle, good_bundle: Bundle
) -> None:
    registry = _registry(build_service, northwind, good_bundle)
    result = registry.call_tool(
        "northwind", "find_concepts", {"query": "customer lifetime value", "k": 10}
    )
    ids = {candidate["concept_id"] for candidate in result["candidates"]}
    assert not ids & set(good_bundle.concepts)


def test_duplicate_bundle_ids_are_rejected(
    build_service: ServiceFactory, northwind: Bundle
) -> None:
    with pytest.raises(ValueError, match="duplicate"):
        BundleRegistry(
            [
                BundleRegistration("dup", build_service(northwind)),
                BundleRegistration("dup", build_service(northwind)),
            ]
        )


def test_an_empty_registry_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least one"):
        BundleRegistry([])


@pytest.mark.parametrize("bad_id", ["", "  ", "a/b", "../escape"])
def test_a_blank_or_path_like_bundle_id_is_rejected(
    build_service: ServiceFactory, northwind: Bundle, bad_id: str
) -> None:
    with pytest.raises(ValueError):
        BundleRegistration(bad_id, build_service(northwind))


def test_build_bundles_dir_registry_rejects_an_unknown_access_map_bundle_id(
    tmp_path: Path,
) -> None:
    # A typo'd or stale --bundle-access entry must fail closed at startup,
    # not silently apply to nothing while the intended bundle serves unlabeled.
    bundles_dir = tmp_path / "bundles"
    (bundles_dir / "alpha").mkdir(parents=True)

    with pytest.raises(ValueError, match="unknown bundle id"):
        build_bundles_dir_registry(bundles_dir, access_by_bundle={"ghost": "confidential"})
