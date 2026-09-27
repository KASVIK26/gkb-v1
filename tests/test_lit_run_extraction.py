"""End-to-end tests for curator/lit/run_extraction.py -- Europe PMC and the LLM are both mocked."""

from __future__ import annotations

import json

from curator.lit import europepmc
from curator.lit.run_extraction import _strip_markdown_fence, extract_paper
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
        self.call_count = 0

    def complete(self, system, user, *, model, temperature=0.0):
        self.call_count += 1
        return LLMResponse(content=self._content, model="fake-model", prompt_tokens=1, completion_tokens=1, cached=False)


class _SequentialFakeLLMClient:
    """Returns a different canned response per call, in order -- for testing the retry path
    (the real extraction call, then the retry call, get genuinely different LLM responses)."""

    def __init__(self, contents: list[str]):
        self._contents = contents
        self.call_count = 0

    def complete(self, system, user, *, model, temperature=0.0):
        content = self._contents[min(self.call_count, len(self._contents) - 1)]
        self.call_count += 1
        return LLMResponse(content=content, model="fake-model", prompt_tokens=1, completion_tokens=1, cached=False)


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
    fulltext_xml = f"<article><body><sec><title>Results</title><p>{fulltext_marker}</p></sec></body></article>"
    monkeypatch.setattr(
        europepmc, "get_record", lambda identifier: _fake_record(isOpenAccess="Y", pmcid="PMC123")
    )
    monkeypatch.setattr(europepmc, "fetch_fulltext_xml", lambda pmcid: fulltext_xml)
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


def test_strip_markdown_fence_removes_json_fence():
    fenced = '```json\n[{"a": 1}]\n```'
    assert _strip_markdown_fence(fenced) == '[{"a": 1}]'


def test_strip_markdown_fence_removes_bare_fence():
    fenced = '```\n[{"a": 1}]\n```'
    assert _strip_markdown_fence(fenced) == '[{"a": 1}]'


def test_strip_markdown_fence_leaves_unfenced_content_alone():
    assert _strip_markdown_fence('[{"a": 1}]') == '[{"a": 1}]'


def test_extract_paper_accepts_a_fenced_json_response(monkeypatch):
    # Real bug found live on a real full-paper run (PHASES.md item 33): the model wrapped an
    # otherwise complete, well-formed JSON array in a ```json ... ``` fence despite the prompt
    # explicitly saying not to -- previously rejected outright as "invalid JSON".
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
    fenced_content = "```json\n" + json.dumps(candidates) + "\n```"
    result = extract_paper(
        "pmid:34897256", crop="wheat", llm_client=_FakeLLMClient(fenced_content), bundle=toy_bundle()
    )
    assert len(result.accepted) == 1
    assert len(result.rejected) == 0


def test_extract_paper_falls_back_to_abstract_on_malformed_fulltext_xml(monkeypatch):
    # Real bug found live (PHASES.md item 33): fetch_fulltext_xml's result was previously sent
    # straight to the LLM with no parsing at all. Now that it's parsed as JATS XML, malformed XML
    # must fall back to the abstract rather than crash or silently send tag soup.
    monkeypatch.setattr(
        europepmc, "get_record", lambda identifier: _fake_record(isOpenAccess="Y", pmcid="PMC123")
    )
    monkeypatch.setattr(europepmc, "fetch_fulltext_xml", lambda pmcid: "<not><valid</xml")
    candidates = [{
        "claim_type": "GENE_CONFERS_RESISTANCE",
        "subject": {"type": "Gene", "text": "TestYr1"},
        "object": {"type": "Disease", "text": "stripe rust"},
        "qualifiers": {"resistance_type": "unknown"},
        "evidence": {
            "quote": "TestYr1 confers all-stage resistance to stripe rust in wheat under field conditions.",
            "section": "abstract",
        },
    }]
    result = extract_paper(
        "pmid:34897256", crop="wheat", llm_client=_FakeLLMClient(json.dumps(candidates)), bundle=toy_bundle()
    )
    assert len(result.accepted) == 1  # grounded against the abstract, since the "full text" was unusable


# ─────────────────────── retry=True (opt-in corrective pass) ───────────────────────

_RETRY_TEXT = "Stripe rust is a major wheat disease. TestYr1 has provided resistance to this pathogen for many seasons."


def _ungrounded_candidate() -> list[dict]:
    # Real bug pattern from the 5-paper pilot (PHASES.md item 30): the disease name is only in the
    # preceding sentence, so a quote that only covers the resistance sentence never mentions it.
    return [{
        "claim_type": "GENE_CONFERS_RESISTANCE",
        "subject": {"type": "Gene", "text": "TestYr1"},
        "object": {"type": "Disease", "text": "stripe rust"},
        "qualifiers": {"resistance_type": "unknown"},
        "evidence": {"quote": "TestYr1 has provided resistance to this pathogen for many seasons.", "section": "abstract"},
    }]


def test_extract_paper_retry_fixes_a_previously_ungrounded_candidate(monkeypatch):
    monkeypatch.setattr(europepmc, "get_record", lambda identifier: _fake_record(abstractText=_RETRY_TEXT))
    corrected = {
        "claim_type": "GENE_CONFERS_RESISTANCE",
        "subject": {"type": "Gene", "text": "TestYr1"},
        "object": {"type": "Disease", "text": "stripe rust"},
        "qualifiers": {"resistance_type": "unknown"},
        "evidence": {"quote": _RETRY_TEXT, "section": "abstract"},
    }
    llm_client = _SequentialFakeLLMClient([json.dumps(_ungrounded_candidate()), json.dumps(corrected)])

    result = extract_paper("pmid:34897256", crop="wheat", llm_client=llm_client, bundle=toy_bundle(), retry=True)

    assert len(result.accepted) == 1
    assert len(result.rejected) == 0
    assert result.accepted[0].evidence.extractor.endswith("+retry")
    assert llm_client.call_count == 2


def test_extract_paper_retry_disabled_by_default(monkeypatch):
    monkeypatch.setattr(europepmc, "get_record", lambda identifier: _fake_record(abstractText=_RETRY_TEXT))
    llm_client = _SequentialFakeLLMClient([json.dumps(_ungrounded_candidate()), json.dumps([])])

    result = extract_paper("pmid:34897256", crop="wheat", llm_client=llm_client, bundle=toy_bundle())

    assert len(result.accepted) == 0
    assert len(result.rejected) == 1
    assert llm_client.call_count == 1  # retry=False (default) never calls .complete() a second time


def test_extract_paper_retry_returns_null_stays_rejected(monkeypatch):
    monkeypatch.setattr(europepmc, "get_record", lambda identifier: _fake_record(abstractText=_RETRY_TEXT))
    llm_client = _SequentialFakeLLMClient([json.dumps(_ungrounded_candidate()), "null"])

    result = extract_paper("pmid:34897256", crop="wheat", llm_client=llm_client, bundle=toy_bundle(), retry=True)

    assert len(result.accepted) == 0
    assert len(result.rejected) == 1
    assert "does not mention" in result.rejected[0].reason


def test_extract_paper_retry_invalid_response_falls_back_to_original_rejection(monkeypatch):
    monkeypatch.setattr(europepmc, "get_record", lambda identifier: _fake_record(abstractText=_RETRY_TEXT))
    llm_client = _SequentialFakeLLMClient([json.dumps(_ungrounded_candidate()), "not valid json"])

    result = extract_paper("pmid:34897256", crop="wheat", llm_client=llm_client, bundle=toy_bundle(), retry=True)

    assert len(result.accepted) == 0
    assert len(result.rejected) == 1
    assert "does not mention" in result.rejected[0].reason
