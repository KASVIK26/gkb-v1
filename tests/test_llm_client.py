"""Unit tests for curator/llm/client.py -- mocked HTTP, no live API calls, no live API key needed."""

from __future__ import annotations

import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from curator.llm.client import (
    DEFAULT_MODEL,
    GEMINI_DEFAULT_MODEL,
    GEMINI_URL,
    GROQ_DEFAULT_MODEL,
    GROQ_URL,
    OPENROUTER_URL,
    LLMClient,
    LLMClientError,
)


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


def test_default_provider_is_openrouter(tmp_path):
    client = LLMClient(api_key="test-key", cache_dir=tmp_path)
    assert client._url == OPENROUTER_URL
    with patch("urllib.request.urlopen", return_value=_mock_chat_response("[]")):
        response = client.complete("system", "user")  # no model given -- should use DEFAULT_MODEL
    assert response.model == DEFAULT_MODEL


def test_gemini_provider_uses_gemini_url_and_key(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    client = LLMClient(provider="gemini", cache_dir=tmp_path)
    assert client._url == GEMINI_URL
    with patch("urllib.request.urlopen", return_value=_mock_chat_response("[]")) as mock_open:
        response = client.complete("system", "user")  # no model given -- should use GEMINI_DEFAULT_MODEL
    assert response.model == GEMINI_DEFAULT_MODEL
    called_request = mock_open.call_args[0][0]
    assert called_request.full_url == GEMINI_URL
    assert called_request.headers["Authorization"] == "Bearer gemini-test-key"


def test_gemini_provider_disables_thinking_mode(tmp_path):
    # Without this, gemini-3.5-flash defaults to an invisible "thinking" pass that can burn the
    # whole token budget and return no content at all -- verified live, see module docstring.
    client = LLMClient(provider="gemini", api_key="test-key", cache_dir=tmp_path)
    with patch("urllib.request.urlopen", return_value=_mock_chat_response("[]")) as mock_open:
        client.complete("system", "user")
    called_request = mock_open.call_args[0][0]
    sent_payload = json.loads(called_request.data)
    assert sent_payload["reasoning_effort"] == "none"


def test_gemini_provider_missing_key_raises_with_gemini_message(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    client = LLMClient(provider="gemini", cache_dir=tmp_path)
    with pytest.raises(LLMClientError, match="GEMINI_API_KEY"):
        client.complete("system", "user", model="test-model")


def test_groq_provider_uses_groq_url_and_key(tmp_path, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "groq-test-key")
    client = LLMClient(provider="groq", cache_dir=tmp_path)
    assert client._url == GROQ_URL
    with patch("urllib.request.urlopen", return_value=_mock_chat_response("[]")) as mock_open:
        response = client.complete("system", "user")  # no model given -- should use GROQ_DEFAULT_MODEL
    assert response.model == GROQ_DEFAULT_MODEL
    called_request = mock_open.call_args[0][0]
    assert called_request.full_url == GROQ_URL
    assert called_request.headers["Authorization"] == "Bearer groq-test-key"
    sent_payload = json.loads(called_request.data)
    assert "reasoning_effort" not in sent_payload  # that's a gemini-specific quirk, not groq's


def test_groq_provider_missing_key_raises_with_groq_message(tmp_path, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    client = LLMClient(provider="groq", cache_dir=tmp_path)
    with pytest.raises(LLMClientError, match="GROQ_API_KEY"):
        client.complete("system", "user", model="test-model")


def test_unknown_provider_raises_valueerror(tmp_path):
    with pytest.raises(ValueError, match="Unknown provider"):
        LLMClient(provider="not-a-real-provider", cache_dir=tmp_path)


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
