"""Unit tests for curator/llm/client.py -- mocked HTTP, no live API calls, no live API key needed."""

from __future__ import annotations

import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from curator.llm.client import LLMClient, LLMClientError


def _mock_chat_response(content: str, *, prompt_tokens=10, completion_tokens=5):
    body = {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
    }
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(body).encode("utf-8")
    mock_response.__enter__.return_value = mock_response
    mock_response.__exit__.return_value = False
    return mock_response


def test_complete_calls_api_and_returns_content(tmp_path):
    client = LLMClient(api_key="test-key", cache_dir=tmp_path)
    with patch("urllib.request.urlopen", return_value=_mock_chat_response("[]")) as mock_open:
        response = client.complete("system prompt", "user text", model="test-model")

    assert response.content == "[]"
    assert response.cached is False
    assert response.prompt_tokens == 10
    mock_open.assert_called_once()


def test_second_identical_call_is_served_from_cache(tmp_path):
    client = LLMClient(api_key="test-key", cache_dir=tmp_path)
    with patch("urllib.request.urlopen", return_value=_mock_chat_response("[]")) as mock_open:
        first = client.complete("system", "user", model="test-model")
        second = client.complete("system", "user", model="test-model")

    assert first.cached is False
    assert second.cached is True
    assert second.content == first.content
    mock_open.assert_called_once()  # the second call made no network request


def test_different_prompt_is_not_a_cache_hit(tmp_path):
    client = LLMClient(api_key="test-key", cache_dir=tmp_path)
    with patch("urllib.request.urlopen", return_value=_mock_chat_response("[]")) as mock_open:
        client.complete("system", "user A", model="test-model")
        client.complete("system", "user B", model="test-model")
    assert mock_open.call_count == 2


def test_retry_on_429_then_success(tmp_path):
    client = LLMClient(api_key="test-key", cache_dir=tmp_path)
    error_429 = urllib.error.HTTPError("url", 429, "Too Many Requests", {}, None)
    with patch("time.sleep"), patch(
        "urllib.request.urlopen", side_effect=[error_429, _mock_chat_response("[]")]
    ) as mock_open:
        response = client.complete("system", "user", model="test-model")

    assert response.content == "[]"
    assert mock_open.call_count == 2


def test_non_retryable_error_raises_immediately(tmp_path):
    client = LLMClient(api_key="test-key", cache_dir=tmp_path)
    error_400 = urllib.error.HTTPError("url", 400, "Bad Request", {}, MagicMock(read=lambda: b"bad request"))
    with patch("urllib.request.urlopen", side_effect=error_400):
        with pytest.raises(LLMClientError, match="400"):
            client.complete("system", "user", model="test-model")


def test_missing_api_key_raises(tmp_path):
    client = LLMClient(api_key="", cache_dir=tmp_path)
    with pytest.raises(LLMClientError, match="OPEN_ROUTER_API_KEY"):
        client.complete("system", "user", model="test-model")


def test_usage_log_gets_a_line_per_call(tmp_path):
    client = LLMClient(api_key="test-key", cache_dir=tmp_path)
    with patch("urllib.request.urlopen", return_value=_mock_chat_response("[]")):
        client.complete("system", "user", model="test-model")
        client.complete("system", "user", model="test-model")  # cache hit, still logged

    log_lines = (tmp_path / "usage.log").read_text(encoding="utf-8").strip().splitlines()
    assert len(log_lines) == 2
    entries = [json.loads(line) for line in log_lines]
    assert entries[0]["cached"] is False
    assert entries[1]["cached"] is True
