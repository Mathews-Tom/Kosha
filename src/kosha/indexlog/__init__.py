"""Index/log generation: keep ``index.md`` and ``log.md`` regenerated.

The indexlog package realizes the deterministic Index/Log generator component
(system_design §2.2): per-directory ``index.md`` regeneration for progressive
disclosure (OKF §6.5) and newest-first dated ``log.md`` append (OKF §6.6).
"""

from __future__ import annotations

from kosha.indexlog.index import (
    bundle_directories,
    directory_of,
    regenerate_index,
    regenerate_indexes,
    write_indexes,
)

__all__ = [
    "bundle_directories",
    "directory_of",
    "regenerate_index",
    "regenerate_indexes",
    "write_indexes",
]
