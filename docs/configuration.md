# Configuration

Kosha is model- and cloud-neutral: embeddings and generation sit behind narrow provider interfaces, selected from the environment. Nothing in the maintenance loop or the benchmark depends on a specific model or vendor.

## Default: local, offline, deterministic

With no configuration, Kosha uses a zero-dependency local pair:

| Surface | Default provider | Notes |
|---|---|---|
| Embedding | `lexical-hash-256` (`LexicalEmbeddingProvider`) | Deterministic hashed-lexical vectors |
| Generation | `extractive-3` (`ExtractiveGenerationProvider`) | Deterministic extractive summaries |

This is why `kosha bench`, `kosha eval`, and the test suite run reproducibly with no network and no API key. The local providers are the right default for development, CI, and the deterministic acceptance gate.

## Opting into a real model provider

Set a base URL to switch a surface to the OpenAI-compatible HTTP provider, which talks to any `/embeddings` + `/chat/completions` endpoint (OpenAI, Ollama, llama.cpp, vLLM, …) over the standard library only.

### Embedding provider

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `KOSHA_EMBED_BASE_URL` | to enable | — | API base URL; empty/unset → local default |
| `KOSHA_EMBED_MODEL` | when base URL set | — | Embedding model name |
| `KOSHA_EMBED_API_KEY` | optional | — | Bearer token |
| `KOSHA_EMBED_DIM` | optional | `1536` | Embedding dimension |

### Generation provider

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `KOSHA_GEN_BASE_URL` | to enable | — | API base URL; empty/unset → local default |
| `KOSHA_GEN_MODEL` | when base URL set | — | Generation model name |
| `KOSHA_GEN_API_KEY` | optional | — | Bearer token |

### Examples

```bash
# OpenAI for generation, local embeddings
export KOSHA_GEN_BASE_URL=https://api.openai.com/v1
export KOSHA_GEN_MODEL=gpt-4o-mini
export KOSHA_GEN_API_KEY=sk-...

# Fully local via Ollama for both surfaces
export KOSHA_EMBED_BASE_URL=http://localhost:11434/v1
export KOSHA_EMBED_MODEL=nomic-embed-text
export KOSHA_GEN_BASE_URL=http://localhost:11434/v1
export KOSHA_GEN_MODEL=llama3.1
```

The two surfaces are independent — configure one, both, or neither.

## Fail-loud, never silent

A base URL **without** its companion model is an error, not a silent fallback:

```text
KOSHA_EMBED_BASE_URL is set but KOSHA_EMBED_MODEL is missing
```

`KOSHA_EMBED_DIM` must parse as an integer or it errors. This is deliberate: a half-configured provider should stop the run, not quietly degrade to the local default and produce surprising results.

## Server configuration

The MCP consumer server reads one extra variable:

| Variable | Purpose |
|---|---|
| `KOSHA_BUNDLE` | Bundle path for `kosha-mcp` when no path argument is given |

```bash
KOSHA_BUNDLE=bundles/northwind uv run kosha-mcp
```

## Cost note

Each ingest runs several model calls (extract, dedup-adjudication in the ambiguous band only, merge, relate, contradict). The deterministic similarity thresholds in the dedup resolver keep the *paid* LLM calls rare — cheap models handle extraction and relation; reserve a stronger model for the ambiguous dedup and contradiction calls. Model the cost per ingest before pointing Kosha at a large source set. See [system design §6](system_design.md).
