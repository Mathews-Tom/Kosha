from kosha.providers.diagnostics import (
    diagnose_embedding_provider,
    diagnose_generation_provider,
    inspect_env_var,
    redact,
)


def test_redact():
    assert redact("") == ""
    assert redact("12345") == "***"
    assert redact("sk-1234567890abcdef") == "sk-1234...cdef"
    assert redact("sk-1234567") == "sk-1234..."
    assert redact("1234567890") == "1234...7890"

def test_inspect_env_var():
    diag = inspect_env_var("KOSHA_API_KEY", {"KOSHA_API_KEY": " sk-1234 "}, is_secret=True)
    assert diag.is_set is True
    assert diag.preview == "sk-1234..."
    assert "Leading or trailing whitespace" in diag.suspicious

def test_inspect_env_var_quotes():
    diag = inspect_env_var("KOSHA_API_KEY", {"KOSHA_API_KEY": '"sk-123"'}, is_secret=True)
    assert diag.is_set is True
    assert "Wrapped in quotes" in diag.suspicious



def test_diagnose_embedding_provider_default():
    diag = diagnose_embedding_provider({})
    assert diag.role == "embedding"
    assert diag.is_configured is False
    assert diag.source == "default"
    assert diag.provider_name == "lexical"
    assert len(diag.errors) == 0

def test_diagnose_embedding_provider_configured():
    env = {
        "KOSHA_EMBED_BASE_URL": "http://localhost:8080/v1",
        "KOSHA_EMBED_MODEL": "nomic-embed-text",
        "KOSHA_EMBED_API_KEY": "sk-1234567890abcdef",
        "KOSHA_EMBED_DIM": "768",
    }
    diag = diagnose_embedding_provider(env)
    assert diag.is_configured is True
    assert diag.source == "env"
    assert len(diag.errors) == 0
    api_key_var = next(v for v in diag.vars if v.key == "KOSHA_EMBED_API_KEY")
    assert api_key_var.preview == "sk-1234...cdef"
    
def test_diagnose_embedding_provider_missing_model():
    env = {
        "KOSHA_EMBED_BASE_URL": "http://localhost:8080/v1",
    }
    diag = diagnose_embedding_provider(env)
    assert diag.is_configured is True
    assert len(diag.errors) == 1
    assert "KOSHA_EMBED_BASE_URL is set but KOSHA_EMBED_MODEL is missing" in diag.errors[0]

def test_diagnose_generation_provider_default():
    diag = diagnose_generation_provider({})
    assert diag.is_configured is False
    assert diag.source == "default"

def test_diagnose_generation_provider_configured():
    env = {
        "KOSHA_GEN_BASE_URL": "http://localhost:8080/v1",
        "KOSHA_GEN_MODEL": "llama-3",
        "KOSHA_GEN_API_KEY": "sk-test...",
    }
    diag = diagnose_generation_provider(env)
    assert diag.is_configured is True
    api_key_var = next(v for v in diag.vars if v.key == "KOSHA_GEN_API_KEY")
    assert api_key_var.preview == "sk-test..."

def test_diagnose_embedding_provider_bad_dim():
    env = {
        "KOSHA_EMBED_BASE_URL": "http://localhost:8080/v1",
        "KOSHA_EMBED_MODEL": "nomic",
        "KOSHA_EMBED_DIM": "not-an-int",
    }
    diag = diagnose_embedding_provider(env)
    assert len(diag.errors) == 1
    assert "KOSHA_EMBED_DIM must be an integer, got 'not-an-int'" in diag.errors[0]
