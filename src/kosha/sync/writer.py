"""Generated section writer and marker primitives."""

from __future__ import annotations

import re


class MissingMarkerError(Exception):
    """Raised when a requested generated section marker is missing from the file."""

class GeneratedSectionWriter:
    """Writes deterministic content inside a generated section marker, preserving outside prose."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.start_marker = f"<!-- kosha:sync:start {name} -->"
        self.end_marker = "<!-- kosha:sync:end -->"

        self._pattern = re.compile(
            re.escape(self.start_marker) + r".*?" + re.escape(self.end_marker),
            re.DOTALL,
        )

    def write_section(self, text: str, content: str) -> str:
        """Replace the content inside the marker with the new content."""
        if self.start_marker not in text or self.end_marker not in text:
            message = f"File missing marker '{self.start_marker}' or '{self.end_marker}'"
            raise MissingMarkerError(message)

        replacement = f"{self.start_marker}\n{content}\n{self.end_marker}"
        # We assume there's exactly one such section per name in the file
        new_text, count = self._pattern.subn(replacement, text)
        if count == 0:
            raise MissingMarkerError(f"Could not find a complete '{self.name}' section to replace.")

        return new_text
