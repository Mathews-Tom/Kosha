"""Secret-like content scanner: block a secret before it becomes a committed,
agent-served concept.

Named ingest sources include Confluence/Slack/Drive exports, so a credential
pasted into a source document survives extraction as ordinary prose today and
lands in a committed concept with no gate at all -- a knowledge base every
future ingest and MCP consumer can read verbatim. This scanner is
deliberately biased toward recall over precision: a false positive costs a
human one review click (the change routes to BLOCK); a false negative ships a
live credential.

Only the detector name is ever retained on a finding -- never the matched
text or even a redacted excerpt -- since a finding flows into the rendered
plan and routing reason a human reads and an ingest may log, and a "redacted"
fragment of a secret is still a fragment of a secret.
"""

from __future__ import annotations

import re

# High-precision, well-known credential formats. A prefix/shape this specific
# essentially never occurs in ordinary prose, so these carry near-zero
# false-positive risk.
_PROVIDER_PATTERNS: dict[str, re.Pattern[str]] = {
    "aws-access-key-id": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "github-token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "slack-token": re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b"),
    "stripe-live-key": re.compile(r"\b[sp]k_live_[0-9A-Za-z]{16,}\b"),
    "google-api-key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "private-key-block": re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |)PRIVATE KEY-----"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
}

# Lower-precision heuristic: a "key/secret/token/password"-shaped assignment
# followed by a plausible credential value. Catches pasted config/env content
# the provider-specific patterns above miss, at the cost of occasionally
# flagging documentation that merely discusses a credential field.
_GENERIC_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_-]?key|secret|token|password|passwd|pwd|access[_-]?key)"
    r"\s*[:=]\s*['\"]?[A-Za-z0-9_\-/+=]{12,}['\"]?"
)


def scan_text(text: str) -> frozenset[str]:
    """Return the set of detector names that matched anywhere in ``text``."""
    hits = {name for name, pattern in _PROVIDER_PATTERNS.items() if pattern.search(text)}
    if _GENERIC_ASSIGNMENT.search(text):
        hits.add("generic-credential-assignment")
    return frozenset(hits)
