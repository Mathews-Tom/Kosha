"""Read-only deterministic checks for generated Kosha public surfaces."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class SyncMismatch:
    """One generated public surface that drifted from its source of truth."""

    surface: str
    path: Path
    message: str
    details: tuple[str, ...] = ()


@dataclass(frozen=True)
class SyncCheckReport:
    """Result of a read-only sync check run."""

    mismatches: tuple[SyncMismatch, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        """Whether every checked surface matches its deterministic source."""

        return not self.mismatches


type SyncChecker = Callable[[Path], Sequence[SyncMismatch]]


def run_sync_check(repo_root: Path, checkers: Sequence[SyncChecker] = ()) -> SyncCheckReport:
    """Run every configured sync checker without mutating repository files."""

    root = repo_root.resolve()
    mismatches: list[SyncMismatch] = []
    for checker in checkers:
        mismatches.extend(checker(root))
    return SyncCheckReport(tuple(mismatches))


def sync_check_json(report: SyncCheckReport) -> dict[str, object]:
    """Return a stable JSON payload for ``kosha sync check --json``."""

    return {
        "ok": report.ok,
        "mismatch_count": len(report.mismatches),
        "mismatches": [
            {
                "surface": mismatch.surface,
                "path": mismatch.path.as_posix(),
                "message": mismatch.message,
                "details": list(mismatch.details),
            }
            for mismatch in report.mismatches
        ],
    }


def render_sync_check_text(report: SyncCheckReport) -> str:
    """Render a concise human-readable sync check result."""

    if report.ok:
        return "Kosha sync check passed: generated surfaces match source-of-truth data."
    lines = ["Kosha sync check failed:"]
    for mismatch in report.mismatches:
        lines.append(f"- {mismatch.path.as_posix()}: {mismatch.surface}: {mismatch.message}")
        lines.extend(f"  - {detail}" for detail in mismatch.details)
    return "\n".join(lines)
