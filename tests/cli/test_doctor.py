from unittest.mock import patch

from kosha.cli import main


def test_doctor_providers_default(capsys):
    with patch("os.environ", {}):
        exit_code = main(["doctor", "providers"])
    
    assert exit_code == 0
    captured = capsys.readouterr().out
    assert "Provider Diagnostics" in captured
    assert "Configured: False" in captured
    assert "Source:     default" in captured
    assert "Identity:   lexical" in captured

def test_doctor_providers_broken_env(capsys):
    env = {
        "KOSHA_EMBED_BASE_URL": "http://localhost:8080/v1",
        "KOSHA_EMBED_API_KEY": "sk-secret12345",
    }
    with patch("os.environ", env):
        exit_code = main(["doctor", "providers"])
        
    assert exit_code == 1
    captured = capsys.readouterr().out
    assert "Errors:" in captured
    assert "KOSHA_EMBED_BASE_URL is set but KOSHA_EMBED_MODEL is missing" in captured
    # Secret must not be exposed
    assert "sk-secret12345" not in captured
    assert "sk-secr..." in captured

