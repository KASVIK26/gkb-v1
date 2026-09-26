"""End-to-end tests for curator/lit/run_extraction.py -- Europe PMC and the LLM are both mocked."""

from __future__ import annotations

import json

from curator.lit import europepmc
from curator.lit.run_extraction import extract_paper
from curator.llm.client import LLMResponse

from kg_toy import STRIPE, YR1, toy_bundle

ABSTRACT = (
    "TestYr1 confers all-stage resistance to stripe rust in wheat under field conditions. "
    "This is the paper's own three-season screening trial at two locations."
)


def _fake_record(**overrides) -> dict:
    record = {
        "pmid": "34897256",
        "title": "A test paper about TestYr1",
        "journalTitle": "Test Journal",
        "pubYear": "2022",
        "isOpenAccess": "N",
        "pmcid": None,
        "abstractText": ABSTRACT,
    }
    record.update(overrides)
    return record


class _FakeLLMClient:
    def __init__(self, content: str):
        self._content = content

    def complete(self, system, user, *, model, temperature=0.0):
        return LLMResponse(content=self._content, model="fake-model", prompt_tokens=1, completion_tokens=1, cached=False)


def test_extract_paper_accepts_a_grounded_candidate(monkeypatch):
    monkeypatch.setattr(europepmc, "get_record", lambda identifier: _fake_record())
    candidates = [{
        "claim_type": "GENE_CONFERS_RESISTANCE",
        "subject": {"type": "Gene", "text": "TestYr1"},
        "object": {"type": "Disease", "text": "stripe rust"},
        "qualifiers": {"resistance_type": "ASR"},
        "evidence": {
            "quote": "TestYr1 confers all-stage resistance to stripe rust in wheat under field conditions.",
            "section": "abstract",
        },
    }]
    llm_client = _FakeLLMClient(json.dumps(candidates))

    result = extract_paper("pmid:34897256", crop="wheat", llm_client=llm_client, bundle=toy_bundle())

    assert len(result.accepted) == 1
    assert len(result.rejected) == 0
    accepted = result.accepted[0]
    assert accepted.claim.subject_id == YR1
    assert accepted.claim.object_id == STRIPE
    assert accepted.evidence.source_id == "pmid:34897256"
    assert accepted.evidence.extractor == "llm:fake-model@claim_extraction_v1"
    assert result.source.verified is True
    assert result.source.title == "A test paper about TestYr1"


def test_extract_paper_rejects_ungrounded_quote(monkeypatch):
    monkeypatch.setattr(europepmc, "get_record", lambda identifier: _fake_record())
    candidates = [{
        "claim_type": "GENE_CONFERS_RESISTANCE",
        "subject": {"type": "Gene", "text": "TestYr1"},
        "object": {"type": "Disease", "text": "stripe rust"},
        "qualifiers": {},
        "evidence": {"quote": "This fact was actually never stated anywhere in the source text.", "section": "abstract"},
    }]
    llm_client = _FakeLLMClient(json.dumps(candidates))

    result = extract_paper("pmid:34897256", crop="wheat", llm_client=llm_client, bundle=toy_bundle())

    assert len(result.accepted) == 0
    assert len(result.rejected) == 1
    assert "does not match" in result.rejected[0].reason


def test_extract_paper_rejects_unresolvable_entity(monkeypatch):
    candidates = [{
        "claim_type": "GENE_CONFERS_RESISTANCE",
        "subject": {"type": "Gene", "text": "SomeUnknownGene"},
        "object": {"type": "Disease", "text": "stripe rust"},
        "qualifiers": {},
        "evidence": {
            "quote": "SomeUnknownGene confers all-stage resistance to stripe rust in an unrelated sentence.",
            "section": "abstract",
        },
    }]
    llm_client = _FakeLLMClient(json.dumps(candidates))
    record = _fake_record(abstractText=ABSTRACT + " SomeUnknownGene confers all-stage resistance to stripe rust in an unrelated sentence.")
    monkeypatch.setattr(europepmc, "get_record", lambda identifier: record)

    result = extract_paper("pmid:34897256", crop="wheat", llm_client=llm_client, bundle=toy_bundle())

    assert len(result.accepted) == 0
    assert len(result.rejected) == 1
    assert "subject" in result.rejected[0].reason


def test_extract_paper_handles_no_text_available(monkeypatch):
    monkeypatch.setattr(europepmc, "get_record", lambda identifier: _fake_record(abstractText=None))
    result = extract_paper("pmid:34897256", crop="wheat", llm_client=_FakeLLMClient("[]"), bundle=toy_bundle())
    assert result.accepted == []
    assert "no abstract or full text" in result.rejected[0].reason


def test_extract_paper_handles_invalid_llm_json(monkeypatch):
    monkeypatch.setattr(europepmc, "get_record", lambda identifier: _fake_record())
    result = extract_paper("pmid:34897256", crop="wheat", llm_client=_FakeLLMClient("not json"), bundle=toy_bundle())
    assert result.accepted == []
    assert "invalid JSON" in result.rejected[0].reason


def test_extract_paper_prefers_fulltext_when_open_access(monkeypatch):
    fulltext_marker = "TestYr1 confers all-stage resistance to stripe rust in wheat, from the full text version."
    monkeypatch.setattr(
        europepmc, "get_record", lambda identifier: _fake_record(isOpenAccess="Y", pmcid="PMC123")
    )
    monkeypatch.setattr(europepmc, "fetch_fulltext_xml", lambda pmcid: fulltext_marker)
    candidates = [{
        "claim_type": "GENE_CONFERS_RESISTANCE",
        "subject": {"type": "Gene", "text": "TestYr1"},
        "object": {"type": "Disease", "text": "stripe rust"},
        "qualifiers": {"resistance_type": "unknown"},
        "evidence": {"quote": fulltext_marker, "section": "results"},
    }]
    result = extract_paper(
        "pmid:34897256", crop="wheat", llm_client=_FakeLLMClient(json.dumps(candidates)), bundle=toy_bundle()
    )
    assert len(result.accepted) == 1
