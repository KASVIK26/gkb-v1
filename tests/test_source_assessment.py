"""Unit tests for curator/llm/source_assessment.py -- LLM call is a fake, no live network."""

from __future__ import annotations

import json

from curator.llm.client import LLMResponse
from curator.llm.source_assessment import assess_source


class _FakeLLMClient:
    def __init__(self, content: str):
        self._content = content

    def complete(self, system, user, *, model, temperature=0.0):
        return LLMResponse(content=self._content, model="fake-model", prompt_tokens=1, completion_tokens=1, cached=False)


def test_assess_source_parses_relevant_true():
    client = _FakeLLMClient(json.dumps({"relevant": True, "notes": "This is the paper's own field trial."}))
    result = assess_source(
        title="T", venue="V", year=2020, abstract="abstract text", crop="wheat", llm_client=client
    )
    assert result.relevant is True
    assert "field trial" in result.notes


def test_assess_source_parses_relevant_false():
    client = _FakeLLMClient(json.dumps({"relevant": False, "notes": "This paper is about a different crop."}))
    result = assess_source(
        title="T", venue="V", year=2020, abstract="abstract text", crop="wheat", llm_client=client
    )
    assert result.relevant is False


def test_assess_source_handles_invalid_json_without_raising():
    client = _FakeLLMClient("not json at all")
    result = assess_source(
        title="T", venue="V", year=2020, abstract="abstract text", crop="wheat", llm_client=client
    )
    assert result.relevant is None
    assert "Could not parse" in result.notes


def test_assess_source_handles_missing_relevant_key():
    client = _FakeLLMClient(json.dumps({"notes": "only notes, no relevant key"}))
    result = assess_source(
        title="T", venue="V", year=2020, abstract="abstract text", crop="wheat", llm_client=client
    )
    assert result.relevant is None
