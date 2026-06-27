"""Tests for the OpenAI-compatible request builders and response parsers.

Only the pure (no-I/O) request/response helpers are exercised here; the network
calls are opt-in and require a live endpoint.
"""

from __future__ import annotations

import json

import pytest

from kosha.providers.openai_compatible import (
    build_chat_request,
    build_embedding_request,
    parse_chat_response,
    parse_embedding_response,
)


def test_build_embedding_request_targets_endpoint_with_model_and_input() -> None:
    url, headers, body = build_embedding_request(
        "https://api.example.com/v1/", "secret", "embed-3", ["a", "b"]
    )
    assert url == "https://api.example.com/v1/embeddings"
    assert headers["Authorization"] == "Bearer secret"
    assert headers["Content-Type"] == "application/json"
    payload = json.loads(body)
    assert payload == {"model": "embed-3", "input": ["a", "b"]}


def test_build_embedding_request_omits_auth_header_without_key() -> None:
    _, headers, _ = build_embedding_request("https://x/v1", "", "m", ["a"])
    assert "Authorization" not in headers


def test_build_chat_request_includes_context_and_question() -> None:
    url, _, body = build_chat_request(
        "https://x/v1", "k", "gpt-mini", "How long?", "Gold members: 45 days."
    )
    assert url == "https://x/v1/chat/completions"
    payload = json.loads(body)
    assert payload["model"] == "gpt-mini"
    user = payload["messages"][-1]["content"]
    assert "Gold members: 45 days." in user
    assert "How long?" in user


def test_parse_embedding_response_extracts_float_vectors() -> None:
    payload = {"data": [{"embedding": [0, 1, 2]}, {"embedding": [3, 4, 5]}]}
    assert parse_embedding_response(payload) == [[0.0, 1.0, 2.0], [3.0, 4.0, 5.0]]


def test_parse_chat_response_extracts_message_content() -> None:
    payload = {"choices": [{"message": {"role": "assistant", "content": "45 days"}}]}
    assert parse_chat_response(payload) == "45 days"


def test_parse_embedding_response_orders_items_by_index() -> None:
    payload = {
        "data": [
            {"index": 1, "embedding": [9, 9]},
            {"index": 0, "embedding": [1, 1]},
        ]
    }
    assert parse_embedding_response(payload) == [[1.0, 1.0], [9.0, 9.0]]


@pytest.mark.parametrize(
    "payload",
    [
        {"data": "not-a-list"},
        {"data": [{"embedding": "nope"}]},
        {"wrong": "shape"},
    ],
)
def test_parse_embedding_response_rejects_malformed_payloads(payload: object) -> None:
    with pytest.raises(ValueError):
        parse_embedding_response(payload)


def test_parse_chat_response_rejects_empty_choices() -> None:
    with pytest.raises(ValueError, match="choices"):
        parse_chat_response({"choices": []})
