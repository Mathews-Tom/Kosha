"""Typed errors raised by the OKF document I/O layer."""

from __future__ import annotations


class OKFError(Exception):
    """Base class for all OKF document I/O errors."""


class FrontmatterError(OKFError):
    """Raised when a concept document lacks a parseable YAML frontmatter block."""
