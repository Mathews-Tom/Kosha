"""Explicit HTTP refresh, health, and activations endpoints (M8 PR-2).

``registry``/``start_server`` (shared, real northwind/good bundle fixtures)
cover ACL, unknown-bundle, and endpoint-shape behavior that never mutates a
fixture on disk. Content-mutation scenarios (a genuine revision change or a
refresh failure) use their own tmp_path bundle, never the shared fixtures.
"""

from __future__ import annotations

import json
from http.client import HTTPConnection
from pathlib import Path
from typing import Any

from kosha.index.embedding import EmbeddingIndex
from kosha.mcp.service import KoshaKnowledgeService
from kosha.okf.load import load_bundle
from kosha.providers import LexicalEmbeddingProvider
from kosha.server.registry import BundleRegistration, BundleRegistry

StartServer = Any
RunningServer = Any


def _get(conn: HTTPConnection, path: str) -> tuple[int, dict[str, str], bytes]:
    conn.request("GET", path)
    response = conn.getresponse()
    body = response.read()
    return response.status, dict(response.getheaders()), body


def _post(conn: HTTPConnection, path: str) -> tuple[int, dict[str, str], bytes]:
    conn.request("POST", path, body=b"", headers={"Content-Length": "0"})
    response = conn.getresponse()
    return response.status, dict(response.getheaders()), response.read()


def _write_concept(root: Path, *, title: str = "Example") -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "concept.md").write_text(
        f'---\ntype: "policy"\ntitle: {title}\n---\nBody text.\n', encoding="utf-8"
    )


def _service(bundle_root: Path) -> KoshaKnowledgeService:
    bundle = load_bundle(bundle_root)
    index = EmbeddingIndex.build(bundle, LexicalEmbeddingProvider())
    return KoshaKnowledgeService(bundle, index)


def test_post_refresh_on_an_unauthorized_bundle_is_a_403(
    registry: BundleRegistry, start_server: StartServer
) -> None:
    server: RunningServer = start_server(registry)
    status, _, body = _post(server.connection(), "/refresh/good")

    assert status == 403
    assert json.loads(body)["error"]["code"] == "access_denied"


def test_post_refresh_on_an_unknown_bundle_is_a_404(
    registry: BundleRegistry, start_server: StartServer
) -> None:
    server: RunningServer = start_server(registry)
    status, _, body = _post(server.connection(), "/refresh/does-not-exist")

    assert status == 404
    assert json.loads(body)["error"]["code"] == "not_found"


def test_post_refresh_no_op_reports_unchanged(
    registry: BundleRegistry, start_server: StartServer
) -> None:
    server: RunningServer = start_server(registry)
    status, headers, body = _post(server.connection(), "/refresh/northwind")

    assert status == 200
    assert "application/json" in headers.get("Content-Type", "")
    payload = json.loads(body)
    assert payload["changed"] is False
    assert payload["health"] == "current"
    assert payload["error"] is None
    assert payload["revision"] == registry.active_registration("northwind").revision


def test_get_health_reports_only_authorized_bundles(
    registry: BundleRegistry, start_server: StartServer
) -> None:
    server: RunningServer = start_server(registry)
    status, _, body = _get(server.connection(), "/health")

    assert status == 200
    payload = json.loads(body)
    ids = {entry["bundle_id"] for entry in payload["bundles"]}
    assert ids == {"northwind"}  # "good" (confidential, no clearance) is excluded
    (entry,) = payload["bundles"]
    assert entry["health"] == "current"
    assert entry["last_error"] is None
    assert entry["revision"] == registry.active_registration("northwind").revision


def test_get_health_and_activations_never_leak_concept_body_text(
    registry: BundleRegistry, start_server: StartServer
) -> None:
    server: RunningServer = start_server(registry)
    conn = server.connection()
    _, _, health_body = _get(conn, "/health")
    _, _, activations_body = _get(conn, "/activations")

    for body in (health_body, activations_body):
        assert b"3-5 business days" not in body  # a known northwind body fragment


def test_get_activations_excludes_an_unauthorized_bundles_events(
    tmp_path: Path, start_server: StartServer
) -> None:
    public_root = tmp_path / "public"
    locked_root = tmp_path / "locked"
    _write_concept(public_root, title="Public before")
    _write_concept(locked_root, title="Locked before")
    locked_bundle = load_bundle(locked_root)
    locked_service = KoshaKnowledgeService(
        locked_bundle,
        EmbeddingIndex.build(locked_bundle, LexicalEmbeddingProvider()),
        bundle_access="confidential",  # server clearance below never grants this
    )
    registry = BundleRegistry(
        [
            BundleRegistration("public", _service(public_root)),
            BundleRegistration("locked", locked_service),
        ]
    )
    server: RunningServer = start_server(registry)

    _write_concept(public_root, title="Public after")
    _write_concept(locked_root, title="Locked after")
    # refresh() itself has no ACL gate (only the HTTP /refresh endpoint does);
    # both activate so the endpoint's own filtering is what's under test.
    assert registry.refresh("public").changed is True
    assert registry.refresh("locked").changed is True

    _, _, body = _get(server.connection(), "/activations")
    bundle_ids = {entry["bundle_id"] for entry in json.loads(body)["activations"]}

    assert bundle_ids == {"public"}


def test_end_to_end_refresh_updates_bundles_health_and_activations_over_http(
    tmp_path: Path, start_server: StartServer
) -> None:
    root = tmp_path / "bundle"
    _write_concept(root, title="Before")
    registry = BundleRegistry([BundleRegistration("solo", _service(root))])
    server: RunningServer = start_server(registry)
    conn = server.connection()
    old_revision = registry.active_registration("solo").revision

    _write_concept(root, title="After")
    status, _, refresh_body = _post(conn, "/refresh/solo")
    assert status == 200
    outcome = json.loads(refresh_body)
    assert outcome["changed"] is True
    new_revision = outcome["revision"]
    assert new_revision != old_revision

    _, _, bundles_body = _get(conn, "/bundles")
    assert json.loads(bundles_body) == {
        "bundles": [{"bundle_id": "solo", "revision": new_revision}]
    }

    _, _, health_body = _get(conn, "/health")
    (health_entry,) = json.loads(health_body)["bundles"]
    assert health_entry["health"] == "current"
    assert health_entry["revision"] == new_revision

    _, _, activations_body = _get(conn, "/activations")
    (activation,) = json.loads(activations_body)["activations"]
    assert activation == {
        "bundle_id": "solo",
        "revision": new_revision,
        "activated_at": registry.active_registration("solo").activated_at,
    }


def test_refresh_failure_over_http_reports_failed_health_and_preserves_old_content(
    tmp_path: Path, start_server: StartServer
) -> None:
    root = tmp_path / "bundle"
    _write_concept(root, title="Good")
    registry = BundleRegistry([BundleRegistration("solo", _service(root))])
    server: RunningServer = start_server(registry)
    conn = server.connection()
    old_revision = registry.active_registration("solo").revision

    (root / "concept.md").write_text("not frontmatter\n", encoding="utf-8")
    status, _, refresh_body = _post(conn, "/refresh/solo")

    assert status == 200
    outcome = json.loads(refresh_body)
    assert outcome["changed"] is False
    assert outcome["health"] == "failed"
    assert outcome["error"]["stage"] == "load"
    assert outcome["revision"] == old_revision

    _, _, health_body = _get(conn, "/health")
    (health_entry,) = json.loads(health_body)["bundles"]
    assert health_entry["health"] == "failed"
    assert health_entry["last_error"]["stage"] == "load"

    # No activation was recorded for the failed attempt.
    _, _, activations_body = _get(conn, "/activations")
    assert json.loads(activations_body) == {"activations": []}


def test_health_reports_stale_when_source_changes_without_an_explicit_refresh(
    tmp_path: Path, start_server: StartServer
) -> None:
    root = tmp_path / "bundle"
    _write_concept(root, title="Before")
    registry = BundleRegistry([BundleRegistration("solo", _service(root))])
    server: RunningServer = start_server(registry)

    _write_concept(root, title="After")  # on-disk change, no refresh triggered
    status, _, health_body = _get(server.connection(), "/health")

    assert status == 200
    (entry,) = json.loads(health_body)["bundles"]
    assert entry["health"] == "stale"  # never falsely reported as current
