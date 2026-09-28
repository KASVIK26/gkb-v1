"""Unit tests for curator/llm/paper_summary.py -- LLM call is a fake, no live network."""

from __future__ import annotations

import json

from curator.llm.client import LLMResponse
from curator.llm.paper_summary import summarize_paper


class _FakeLLMClient:
    def __init__(self, content: str):
        self._content = content

    def complete(self, system, user, *, model, temperature=0.0):
        return LLMResponse(content=self._content, model="fake-model", prompt_tokens=1, completion_tokens=1, cached=False)


def test_summarize_paper_parses_bullets():
    client = _FakeLLMClient(json.dumps({"bullets": ["TestYr1 confers resistance to stripe rust.", "Trial ran over three seasons."]}))
    result = summarize_paper(title="T", venue="V", year=2020, text="full text", crop="wheat", llm_client=client)
    assert result.bullets == ["TestYr1 confers resistance to stripe rust.", "Trial ran over three seasons."]


def test_summarize_paper_handles_empty_bullets():
    client = _FakeLLMClient(json.dumps({"bullets": []}))
    result = summarize_paper(title="T", venue="V", year=2020, text="full text", crop="wheat", llm_client=client)
    assert result.bullets == []


def test_summarize_paper_handles_invalid_json_without_raising():
    client = _FakeLLMClient("not json at all")
    result = summarize_paper(title="T", venue="V", year=2020, text="full text", crop="wheat", llm_client=client)
    assert result.bullets == []


def test_summarize_paper_handles_missing_bullets_key():
    client = _FakeLLMClient(json.dumps({"notes": "no bullets key here"}))
    result = summarize_paper(title="T", venue="V", year=2020, text="full text", crop="wheat", llm_client=client)
    assert result.bullets == []
