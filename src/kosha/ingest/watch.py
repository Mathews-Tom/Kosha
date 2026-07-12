"""Scheduled ingest runner with explicit source policy gates."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from kosha.evidence import CoverageKind, SourceCoverage
from kosha.ingest.url import UrlIngestError, fetch_url
from kosha.pipeline import IngestResult, ingest

Clock = Callable[[], datetime]


@dataclass(frozen=True)
class SourcePolicy:
    """Fail-closed policy applied before a scheduled source reaches ingest."""

    max_bytes: int = 10 * 1024 * 1024
    allowed_hosts: frozenset[str] = field(default_factory=frozenset)

    def check_url(self, url: str) -> None:
        """Reject URLs outside the explicit host allowlist when one is configured."""

        host = urlsplit(url).hostname
        if self.allowed_hosts and host not in self.allowed_hosts:
            raise UrlIngestError(f"hostname {host!r} is not in the scheduled source allowlist")


@dataclass
class ScheduledIngest:
    """Run guarded ingest once or on an interval for one source and bundle."""

    source: Path | str
    bundle_root: Path
    policy: SourcePolicy
    interval_seconds: float = 60.0
    reviewer: str | None = None
    dry_run: bool = True
    assume_yes: bool = False
    authority: int = 0
    now: Clock | None = None
    _next_run_at: datetime | None = None

    def run_once(self) -> IngestResult:
        """Validate the configured source, then call the existing approval path."""

        asof = self._now()
        if isinstance(self.source, str) and _is_url(self.source):
            self.policy.check_url(self.source)
            raw = fetch_url(
                self.source,
                authority_rank=self.authority,
                max_bytes=self.policy.max_bytes,
            )
            return ingest(
                Path(urlsplit(self.source).hostname or "url"),
                self.bundle_root,
                asof=asof,
                source_authority=self.authority,
                dry_run=self.dry_run,
                assume_yes=self.assume_yes,
                reader=None,
                reviewer=self.reviewer,
                raw_docs=[raw],
                coverage=SourceCoverage(
                    kind=CoverageKind.COMPLETE,
                    scope=f"HTTP response body for {self.source}",
                ),
            )
        source_path = self._materialize_source()
        return ingest(
            source_path,
            self.bundle_root,
            asof=asof,
            source_authority=self.authority,
            dry_run=self.dry_run,
            assume_yes=self.assume_yes,
            reader=None,
            reviewer=self.reviewer,
        )

    def run_pending(self) -> IngestResult | None:
        """Run at most once when the interval has elapsed."""

        current = self._now()
        if self._next_run_at is not None and current < self._next_run_at:
            return None
        result = self.run_once()
        self._next_run_at = current + timedelta(seconds=self.interval_seconds)
        return result

    def _materialize_source(self) -> Path:
        if isinstance(self.source, Path):
            return self.source
        return Path(self.source)

    def _now(self) -> datetime:
        clock = self.now or (lambda: datetime.now(UTC))
        return clock()


def _is_url(source: str) -> bool:
    scheme = urlsplit(source).scheme.lower()
    return scheme in {"http", "https"}
