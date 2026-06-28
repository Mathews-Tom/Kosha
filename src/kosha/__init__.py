"""Kosha — a self-maintaining OKF knowledge engine.

The package version is the single source of truth declared in ``pyproject.toml``
and read back here from the installed distribution metadata.
"""

from __future__ import annotations

from importlib.metadata import version

__version__: str = version("kosha-okf")

__all__ = ["__version__"]
