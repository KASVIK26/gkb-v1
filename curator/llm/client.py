"""A small, provider-agnostic LLM client: one concrete backend (OpenRouter), content-hash
caching, retry/backoff, and per-call token/cost logging.

Backend choice: OpenRouter (OPEN_ROUTER_API_KEY) rather than the old extractor's Groq call --
OpenRouter speaks the same OpenAI-compatible chat-completions wire format (so the request/backoff
shape below is a known-good pattern) but exposes many models, including open-weight ones, through
one key. That directly serves RESEARCH_ROADMAP.md Sec 6.1's later ablation requirement ("at least
one open-weight model for reproducibility") without a second client to write.

Caching and logging live under `data/llm_cache/` by default; pass `cache_dir` to point tests at a
temp directory instead so the test suite never touches real cache state.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import curator.model  # noqa: F401  # ensures curator.model.enums loads before curator.normalize.ids
                                     # (curator.normalize.ids imports curator.model.enums; importing
                                     # curator.normalize.ids first, standalone, is a latent circular
                                     # import -- see curator.model.claims's own import order for why
                                     # this one-liner resolves it without touching either module).
from curator.normalize.ids import content_hash

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "llm_cache"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "meta-llama/llama-3.3-70b-instruct"  # overridable per call for ablations

_MAX_RETRIES = 5
_BASE_WAIT_S = 2
_MAX_WAIT_S = 60
_TIMEOUT_S = 120


class LLMClientError(RuntimeError):
    """Raised on a non-retryable API error, or after exhausting all retries."""


@dataclass(frozen=True)
class LLMResponse:
    content: str
    model: str
    prompt_tokens: int | None
    completion_tokens: int | None
    cached: bool


class LLMClient:
    def __init__(self, *, api_key: str | None = None, cache_dir: Path | str = DEFAULT_CACHE_DIR):
        self._api_key = api_key if api_key is not None else os.environ.get("OPEN_ROUTER_API_KEY", "")
        self._cache_dir = Path(cache_dir)

    def _cache_path(self, cache_key: str) -> Path:
        return self._cache_dir / f"{cache_key.split(':', 1)[-1]}.json"

    def _usage_log_path(self) -> Path:
        return self._cache_dir / "usage.log"

    def _log_usage(self, *, model: str, cache_key: str, response: LLMResponse) -> None:
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        line = json.dumps({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "model": model,
            "cache_key": cache_key,
            "cached": response.cached,
            "prompt_tokens": response.prompt_tokens,
            "completion_tokens": response.completion_tokens,
        }, ensure_ascii=False)
        with self._usage_log_path().open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def _call_api(self, *, system: str, user: str, model: str, temperature: float) -> dict:
        if not self._api_key:
            raise LLMClientError(
                "OPEN_ROUTER_API_KEY is not set. Set it in .env before calling the LLM client."
            )
        payload = json.dumps({
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        }).encode("utf-8")

        for attempt in range(_MAX_RETRIES):
            request = urllib.request.Request(
                OPENROUTER_URL,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._api_key}",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=_TIMEOUT_S) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                if exc.code in (429, 500, 502, 503, 504):
                    wait = min(_BASE_WAIT_S ** (attempt + 1), _MAX_WAIT_S)
                    logger.warning(
                        "LLM API HTTP %d, retrying in %ds (%d/%d)",
                        exc.code, wait, attempt + 1, _MAX_RETRIES,
                    )
                    time.sleep(wait)
                    continue
                body = exc.read().decode("utf-8", errors="replace") if exc.fp else str(exc)
                raise LLMClientError(f"LLM API error {exc.code}: {body}") from exc
            except urllib.error.URLError as exc:
                raise LLMClientError(f"Could not reach the LLM API: {exc.reason}") from exc

        raise LLMClientError(f"LLM API still failing after {_MAX_RETRIES} retries.")

    def complete(
        self,
        system: str,
        user: str,
        *,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.0,
    ) -> LLMResponse:
        """Run one chat completion, transparently cached by (model, system, user, temperature)."""
        cache_key = content_hash(
            "llmcache", {"model": model, "system": system, "user": user, "temperature": temperature}
        )
        cache_path = self._cache_path(cache_key)
        if cache_path.exists():
            cached_body = json.loads(cache_path.read_text(encoding="utf-8"))
            response = LLMResponse(
                content=cached_body["content"],
                model=model,
                prompt_tokens=cached_body.get("prompt_tokens"),
                completion_tokens=cached_body.get("completion_tokens"),
                cached=True,
            )
            self._log_usage(model=model, cache_key=cache_key, response=response)
            return response

        body = self._call_api(system=system, user=user, model=model, temperature=temperature)
        content = body["choices"][0]["message"]["content"]
        usage = body.get("usage", {})
        response = LLMResponse(
            content=content,
            model=model,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            cached=False,
        )

        self._cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps({
            "content": response.content,
            "prompt_tokens": response.prompt_tokens,
            "completion_tokens": response.completion_tokens,
        }, ensure_ascii=False), encoding="utf-8")
        self._log_usage(model=model, cache_key=cache_key, response=response)
        return response
