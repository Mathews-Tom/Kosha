"""OpenAI-compatible HTTP providers built on the standard library only.

These talk to any endpoint exposing ``POST {base_url}/embeddings`` and
``POST {base_url}/chat/completions`` with the OpenAI request/response shape —
OpenAI itself, Azure OpenAI, Ollama, llama.cpp's server, vLLM, etc. — keeping
Kosha model- and cloud-neutral with zero third-party dependencies.

Request building and response parsing are pure functions (no I/O) so they are unit
testable without a live endpoint; only :meth:`embed` / :meth:`generate` perform
network calls, and those are opt-in via the environment (see :mod:`kosha.providers.factory`).
"""

from __future__ import annotations

import json
import urllib.request

from kosha.providers.base import Generation, Usage, Vector
from kosha.providers.tokens import count_tokens

# Network read timeout (seconds) for a single provider call.
_TIMEOUT = 60.0


def build_embedding_request(
    base_url: str, api_key: str, model: str, texts: list[str]
) -> tuple[str, dict[str, str], bytes]:
    """Return the ``(url, headers, body)`` for an embeddings request."""
    url = f"{base_url.rstrip('/')}/embeddings"
    body = json.dumps({"model": model, "input": texts}).encode("utf-8")
    return url, _headers(api_key), body


def build_chat_request(
    base_url: str, api_key: str, model: str, query: str, context: str
) -> tuple[str, dict[str, str], bytes]:
    """Return the ``(url, headers, body)`` for a chat-completions request."""
    url = f"{base_url.rstrip('/')}/chat/completions"
    messages = [
        {
            "role": "system",
            "content": "Answer the question using only the provided context.",
        },
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"},
    ]
    body = json.dumps({"model": model, "messages": messages}).encode("utf-8")
    return url, _headers(api_key), body


def parse_embedding_response(payload: object) -> list[Vector]:
    """Extract embedding vectors from a parsed embeddings response."""
    data = _require_list(_require_mapping(payload, "response").get("data"), "data")
    vectors: list[Vector] = []
    for item in data:
        raw = _require_list(_require_mapping(item, "data item").get("embedding"), "embedding")
        vectors.append([_to_float(value) for value in raw])
    return vectors


def parse_chat_response(payload: object) -> str:
    """Extract the answer text from a parsed chat-completions response."""
    mapping = _require_mapping(payload, "response")
    choices = _require_list(mapping.get("choices"), "choices")
    if not choices:
        raise ValueError("chat response has no choices")
    message = _require_mapping(_require_mapping(choices[0], "choice").get("message"), "message")
    content = message.get("content")
    if not isinstance(content, str):
        raise ValueError("chat response message has no string content")
    return content


class OpenAICompatibleEmbeddingProvider:
    """Embeddings via an OpenAI-compatible ``/embeddings`` endpoint."""

    def __init__(self, base_url: str, api_key: str, model: str, dimension: int) -> None:
        self._base_url = base_url
        self._api_key = api_key
        self._model = model
        self._dimension = dimension

    @property
    def name(self) -> str:
        return f"openai:{self._model}"

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: list[str]) -> list[Vector]:
        url, headers, body = build_embedding_request(
            self._base_url, self._api_key, self._model, texts
        )
        vectors = parse_embedding_response(_post_json(url, headers, body))
        if len(vectors) != len(texts):
            raise ValueError(
                f"provider returned {len(vectors)} vectors for {len(texts)} inputs"
            )
        return vectors


class OpenAICompatibleGenerationProvider:
    """Generation via an OpenAI-compatible ``/chat/completions`` endpoint."""

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self._base_url = base_url
        self._api_key = api_key
        self._model = model

    @property
    def name(self) -> str:
        return f"openai:{self._model}"

    def generate(self, query: str, context: str) -> Generation:
        url, headers, body = build_chat_request(
            self._base_url, self._api_key, self._model, query, context
        )
        text = parse_chat_response(_post_json(url, headers, body))
        usage = Usage(
            prompt_tokens=count_tokens(query) + count_tokens(context),
            completion_tokens=count_tokens(text),
        )
        return Generation(text=text, usage=usage)


def _headers(api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _post_json(url: str, headers: dict[str, str], body: bytes) -> object:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
        raw = response.read().decode("utf-8")
    parsed: object = json.loads(raw)
    return parsed


def _require_mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object for {label}")
    return value


def _require_list(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"expected a JSON array for {label}")
    return value


def _to_float(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("embedding contains a non-numeric value")
    return float(value)
