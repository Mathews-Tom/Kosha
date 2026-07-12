"""Dependency-free polling watcher over registry bundle revisions (M8 PR-2).

No filesystem-watch library and no new dependency: :meth:`BundleWatcher.poll_once`
runs one detect-and-refresh pass over its watched bundle ids by calling
:meth:`~kosha.server.registry.BundleRegistry.refresh` for each -- the registry
itself already no-ops when content is unchanged. ``poll_once`` is synchronous
and takes no thread or sleep, so tests drive it deterministically one tick at a
time; :meth:`~BundleWatcher.start` runs it on a fixed interval in a background
daemon thread for production use, with the clock and the activation callback
both injectable.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterable
from datetime import datetime

from kosha.server.registry import BundleRegistry
from kosha.server.revision import ActivationEvent, RefreshOutcome, default_clock


class BundleWatcher:
    """Polls a registry's watched bundles for on-disk revision changes."""

    def __init__(
        self,
        registry: BundleRegistry,
        bundle_ids: Iterable[str] | None = None,
        *,
        clock: Callable[[], datetime] = default_clock,
        on_activation: Callable[[ActivationEvent], None] | None = None,
    ) -> None:
        self._registry = registry
        self._bundle_ids = (
            tuple(bundle_ids) if bundle_ids is not None else tuple(registry.bundle_ids())
        )
        self._clock = clock
        self._on_activation = on_activation
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def bundle_ids(self) -> tuple[str, ...]:
        """The bundle ids this watcher polls, fixed at construction time."""

        return self._bundle_ids

    def poll_once(self) -> tuple[RefreshOutcome, ...]:
        """Run exactly one detect-and-refresh pass over every watched bundle.

        Synchronous, no sleep, no thread -- one bundle's failure never skips or
        corrupts another's poll, since each is an independent
        :meth:`BundleRegistry.refresh` call. The activation callback (if any)
        fires only for a bundle whose revision actually changed, strictly
        after that bundle's swap -- never for a no-op or a failed attempt.
        """

        outcomes: list[RefreshOutcome] = []
        for bundle_id in self._bundle_ids:
            outcome = self._registry.refresh(bundle_id, clock=self._clock)
            outcomes.append(outcome)
            if outcome.changed and self._on_activation is not None:
                for event in self._registry.activation_events(bundle_id)[-1:]:
                    self._on_activation(event)
        return tuple(outcomes)

    def start(self, interval_seconds: float) -> None:
        """Run :meth:`poll_once` every ``interval_seconds`` in a background daemon thread."""

        if self._thread is not None:
            raise RuntimeError("watcher already started")
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")

        def _loop() -> None:
            while not self._stop.wait(interval_seconds):
                self.poll_once()

        self._stop.clear()
        thread = threading.Thread(target=_loop, daemon=True, name="kosha-bundle-watcher")
        self._thread = thread
        thread.start()

    def stop(self) -> None:
        """Stop the background polling thread, if running, and wait for it to exit."""

        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=5)
            self._thread = None
