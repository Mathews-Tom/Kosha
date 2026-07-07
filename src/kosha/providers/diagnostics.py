"""Diagnostics and redaction for provider configurations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


def redact(secret: str) -> str:
    """Mask a secret value for safe logging."""
    if not secret:
        return ""
    stripped = secret.strip()
    if len(stripped) <= 5:
        return "***"
    if stripped.startswith("sk-"):
        prefix = stripped[:7] # sk- + 4 chars
        suffix = stripped[-4:] if len(stripped) > 11 else ""
        return f"{prefix}...{suffix}"
    prefix = stripped[:4]
    suffix = stripped[-4:] if len(stripped) > 8 else ""
    return f"{prefix}...{suffix}"


@dataclass(frozen=True)
class EnvVarDiagnostic:
    """Status of a single environment variable."""
    key: str
    is_set: bool
    preview: str
    suspicious: list[str]


def inspect_env_var(
    key: str, env: Mapping[str, str], is_secret: bool = False
) -> EnvVarDiagnostic:
    """Inspect an environment variable for presence and formatting."""
    raw = env.get(key)
    if raw is None:
        return EnvVarDiagnostic(key=key, is_set=False, preview="", suspicious=[])

    if not raw:
        return EnvVarDiagnostic(key=key, is_set=True, preview="", suspicious=["Empty string"])

    suspicious = []
    if raw != raw.strip():
        suspicious.append("Leading or trailing whitespace")
    
    stripped = raw.strip()
    has_quotes = (
        (stripped.startswith('"') and stripped.endswith('"')) or
        (stripped.startswith("'") and stripped.endswith("'"))
    )
    if has_quotes:
        suspicious.append("Wrapped in quotes")
    
    if key.endswith("_BASE_URL") and stripped.endswith("/"):
        suspicious.append("Trailing slash in base URL")

    preview = redact(raw) if is_secret else stripped
    
    return EnvVarDiagnostic(key=key, is_set=True, preview=preview, suspicious=suspicious)

@dataclass(frozen=True)
class ProviderDiagnostic:
    """Diagnostics for a provider configuration."""
    role: str
    is_configured: bool
    source: str
    provider_name: str
    vars: list[EnvVarDiagnostic]
    errors: list[str]

def diagnose_embedding_provider(env: Mapping[str, str] | None = None) -> ProviderDiagnostic:
    """Diagnose the embedding provider configuration."""
    import os
    source = os.environ if env is None else env
    
    vars_diag = []
    base_url_diag = inspect_env_var("KOSHA_EMBED_BASE_URL", source)
    vars_diag.append(base_url_diag)
    
    errors = []
    if not base_url_diag.preview:
        is_configured = False
        source_label = "default"
        provider_name = "lexical"
    else:
        is_configured = True
        source_label = "env"
        provider_name = "openai_compatible"
        
        model_diag = inspect_env_var("KOSHA_EMBED_MODEL", source)
        vars_diag.append(model_diag)
        if not model_diag.preview:
            errors.append("KOSHA_EMBED_BASE_URL is set but KOSHA_EMBED_MODEL is missing")
            
        api_key_diag = inspect_env_var("KOSHA_EMBED_API_KEY", source, is_secret=True)
        vars_diag.append(api_key_diag)
        
        dim_diag = inspect_env_var("KOSHA_EMBED_DIM", source)
        vars_diag.append(dim_diag)
        if dim_diag.preview:
            try:
                int(dim_diag.preview)
            except ValueError:
                errors.append(f"KOSHA_EMBED_DIM must be an integer, got {dim_diag.preview!r}")
                
    return ProviderDiagnostic(
        role="embedding",
        is_configured=is_configured,
        source=source_label,
        provider_name=provider_name,
        vars=vars_diag,
        errors=errors
    )

def diagnose_generation_provider(env: Mapping[str, str] | None = None) -> ProviderDiagnostic:
    """Diagnose the generation provider configuration."""
    import os
    source = os.environ if env is None else env
    
    vars_diag = []
    base_url_diag = inspect_env_var("KOSHA_GEN_BASE_URL", source)
    vars_diag.append(base_url_diag)
    
    errors = []
    if not base_url_diag.preview:
        is_configured = False
        source_label = "default"
        provider_name = "extractive"
    else:
        is_configured = True
        source_label = "env"
        provider_name = "openai_compatible"
        
        model_diag = inspect_env_var("KOSHA_GEN_MODEL", source)
        vars_diag.append(model_diag)
        if not model_diag.preview:
            errors.append("KOSHA_GEN_BASE_URL is set but KOSHA_GEN_MODEL is missing")
            
        api_key_diag = inspect_env_var("KOSHA_GEN_API_KEY", source, is_secret=True)
        vars_diag.append(api_key_diag)
        
    return ProviderDiagnostic(
        role="generation",
        is_configured=is_configured,
        source=source_label,
        provider_name=provider_name,
        vars=vars_diag,
        errors=errors
    )
