"""Deterministic bundle content revisions (M8 PR-1).

:func:`compute_bundle_revision` is a thin, deliberate reuse of
``kosha.sync.snapshot.content_snapshot`` -- the source spec forbids inventing
a second, incompatible hash convention for serving revisions.
"""

from __future__ import annotations

from pathlib import Path

from kosha.server.revision import compute_bundle_revision, resolve_source_git_head
from kosha.sync.snapshot import content_snapshot


def _write_concept(root: Path, *, title: str = "Example") -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "concept.md").write_text(
        f"---\ntype: policy\ntitle: {title}\n---\nBody text.\n", encoding="utf-8"
    )


def test_compute_bundle_revision_delegates_to_the_shared_content_snapshot(
    tmp_path: Path,
) -> None:
    _write_concept(tmp_path)
    assert compute_bundle_revision(tmp_path) == content_snapshot(tmp_path).sha256


def test_compute_bundle_revision_is_stable_for_identical_content(tmp_path: Path) -> None:
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    _write_concept(root_a, title="Same")
    _write_concept(root_b, title="Same")
    assert compute_bundle_revision(root_a) == compute_bundle_revision(root_b)


def test_compute_bundle_revision_changes_when_content_changes(tmp_path: Path) -> None:
    _write_concept(tmp_path, title="Before")
    before = compute_bundle_revision(tmp_path)
    _write_concept(tmp_path, title="After")
    after = compute_bundle_revision(tmp_path)
    assert before != after


def test_resolve_source_git_head_is_none_outside_a_git_work_tree(tmp_path: Path) -> None:
    _write_concept(tmp_path)
    assert resolve_source_git_head(tmp_path) is None


def test_resolve_source_git_head_returns_head_inside_this_repository() -> None:
    # bundles/northwind lives inside the Kosha repository itself.
    repo_bundle = Path(__file__).resolve().parents[2] / "bundles" / "northwind"
    head = resolve_source_git_head(repo_bundle)
    assert head is not None
    assert len(head) == 40  # a full SHA-1 hex commit id
