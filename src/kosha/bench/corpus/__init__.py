"""External benchmark corpus generation (DEVELOPMENT_PLAN §7 M13).

The real-model benchmark needs an *external, not-Kosha-authored* corpus of
500-2,000 concepts. :mod:`kosha.bench.corpus.stdlib` renders one deterministically
from the CPython standard library's own docstrings; the committed
``bundles/pydoc-stdlib/`` bundle is the benchmark's source of truth and this
package is its provenance.
"""

from __future__ import annotations

from kosha.bench.corpus.stdlib import (
    CORPUS_NAME,
    MODULES,
    MODULES_XL,
    SCALED_MAX_MEMBERS,
    CorpusEntry,
    CorpusStats,
    build_corpus,
    build_scaled_corpus,
    collect_entries,
)

__all__ = [
    "CORPUS_NAME",
    "MODULES",
    "MODULES_XL",
    "SCALED_MAX_MEMBERS",
    "CorpusEntry",
    "CorpusStats",
    "build_corpus",
    "build_scaled_corpus",
    "collect_entries",
]
