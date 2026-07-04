"""Secret-like content scanner: detection without retaining the secret (M6 PR-6)."""

from __future__ import annotations

from kosha.security.secret_scan import scan_text


def test_clean_prose_has_no_findings() -> None:
    text = "Standard returns are accepted within 30 days of delivery."
    assert scan_text(text) == frozenset()


def test_detects_aws_access_key_id() -> None:
    text = "export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE"
    assert "aws-access-key-id" in scan_text(text)


def test_detects_github_token() -> None:
    text = "token: ghp_" + "a" * 36
    assert "github-token" in scan_text(text)


def test_detects_slack_token() -> None:
    text = "SLACK_BOT_TOKEN=xoxb-1234567890-abcdefghijk"
    assert "slack-token" in scan_text(text)


def test_detects_stripe_live_key() -> None:
    text = "sk_live_" + "a" * 24
    assert "stripe-live-key" in scan_text(text)


def test_detects_google_api_key() -> None:
    text = "AIza" + "a" * 35
    assert "google-api-key" in scan_text(text)


def test_detects_private_key_block() -> None:
    text = "-----BEGIN RSA PRIVATE KEY-----\nMIIB...\n-----END RSA PRIVATE KEY-----"
    assert "private-key-block" in scan_text(text)


def test_detects_jwt() -> None:
    header = "eyJhbGciOiJIUzI1NiIs"
    payload = "eyJzdWIiOiIxMjM0NTY3ODkwIn0"
    signature = "dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
    text = f"Authorization: Bearer {header}.{payload}.{signature}"
    assert "jwt" in scan_text(text)


def test_detects_generic_credential_assignment() -> None:
    text = 'api_key: "sk-abcdefghijklmnopqrstuvwxyz123456"'
    assert "generic-credential-assignment" in scan_text(text)


def test_findings_never_retain_the_matched_text() -> None:
    # SecretFinding is intentionally not a thing: only detector names survive,
    # never a copy (redacted or otherwise) of the secret itself.
    findings = scan_text("AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE")
    assert findings == frozenset({"aws-access-key-id"})
    assert all(isinstance(name, str) and "AKIA" not in name for name in findings)


def test_multiple_distinct_secrets_all_detected() -> None:
    text = "\n".join(
        [
            "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE",
            "token: ghp_" + "b" * 36,
        ]
    )
    findings = scan_text(text)
    assert "aws-access-key-id" in findings
    assert "github-token" in findings
