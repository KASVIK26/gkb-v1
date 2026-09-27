"""Tests for curator/extract/langextract_pipeline.py -- LangExtract itself is mocked (monkeypatch
`langextract.extract`), so this suite has no live network/LLM dependency. It proves the adapter's
own logic (mapping an Extraction to our raw candidate shape, honoring char_interval/entity-presence
grounding, deduping across multi-pass extraction) rather than LangExtract's own internals, which
have their own upstream test suite.
"""

from __future__ import annotations

import langextract as lx
import pytest

from curator.extract.langextract_pipeline import _extraction_to_raw, extract_paper_langextract
from curator.lit import europepmc

from kg_toy import STRIPE, YR1, toy_bundle


def _fake_record(**overrides) -> dict:
    record = {
        "pmid": "34897256", "title": "A test paper about TestYr1", "journalTitle": "Test Journal",
        "pubYear": "2022", "isOpenAccess": "N", "pmcid": None,
        "abstractText": "Stripe rust is a major wheat disease. TestYr1 has provided resistance to this pathogen for many seasons.",
    }
    record.update(overrides)
    return record


def _extraction(*, char_interval, alignment_status, subject="TestYr1", obj="stripe rust", quote=None):
    quote = quote or "Stripe rust is a major wheat disease. TestYr1 has provided resistance to this pathogen for many seasons."
    return lx.data.Extraction(
        extraction_class="GENE_CONFERS_RESISTANCE",
        extraction_text=quote,
        char_interval=char_interval,
        alignment_status=alignment_status,
        attributes={
            "subject_type": "Gene", "subject_text": subject,
            "object_type": "Disease", "object_text": obj,
            "resistance_type": "unknown",
        },
    )


def _fake_document(extractions):
    return lx.data.AnnotatedDocument(extractions=list(extractions))


def test_extraction_to_raw_maps_attributes_correctly():
    extraction = _extraction(char_interval=lx.data.CharInterval(0, 10), alignment_status=lx.data.AlignmentStatus.MATCH_EXACT)
    raw = _extraction_to_raw(extraction)
    assert raw["claim_type"] == "GENE_CONFERS_RESISTANCE"
    assert raw["subject"] == {"type": "Gene", "text": "TestYr1"}
    assert raw["object"] == {"type": "Disease", "text": "stripe rust"}
    assert raw["qualifiers"] == {"resistance_type": "unknown"}


def test_accepts_a_well_aligned_extraction(monkeypatch):
    monkeypatch.setattr(europepmc, "get_record", lambda identifier: _fake_record())
    extraction = _extraction(char_interval=lx.data.CharInterval(0, 10), alignment_status=lx.data.AlignmentStatus.MATCH_EXACT)
    monkeypatch.setattr(lx, "extract", lambda **kwargs: _fake_document([extraction]))

    result = extract_paper_langextract("pmid:34897256", crop="wheat", api_key="fake", bundle=toy_bundle())

    assert len(result.accepted) == 1
    assert len(result.rejected) == 0
    accepted = result.accepted[0]
    assert accepted.claim.subject_id == YR1
    assert accepted.claim.object_id == STRIPE
    assert accepted.grounding_score == 100.0
    assert accepted.evidence.extractor.endswith("@langextract_v1")


def test_rejects_extraction_with_no_char_interval(monkeypatch):
    # This is LangExtract's own automatic non-grounded-content filter firing -- the model likely
    # copied from a few-shot example rather than the real input text.
    monkeypatch.setattr(europepmc, "get_record", lambda identifier: _fake_record())
    extraction = _extraction(char_interval=None, alignment_status=None)
    monkeypatch.setattr(lx, "extract", lambda **kwargs: _fake_document([extraction]))

    result = extract_paper_langextract("pmid:34897256", crop="wheat", api_key="fake", bundle=toy_bundle())

    assert len(result.accepted) == 0
    assert len(result.rejected) == 1
    assert "could not align" in result.rejected[0].reason


def test_rejects_extraction_missing_entity_from_its_own_quote(monkeypatch):
    monkeypatch.setattr(europepmc, "get_record", lambda identifier: _fake_record())
    # A real, if unlikely, failure shape: LangExtract aligned the extraction_text somewhere real,
    # but the object it named isn't actually in that specific quoted span.
    extraction = _extraction(
        char_interval=lx.data.CharInterval(0, 10), alignment_status=lx.data.AlignmentStatus.MATCH_EXACT,
        obj="powdery mildew", quote="TestYr1 has provided resistance to this pathogen for many seasons.",
    )
    monkeypatch.setattr(lx, "extract", lambda **kwargs: _fake_document([extraction]))

    result = extract_paper_langextract("pmid:34897256", crop="wheat", api_key="fake", bundle=toy_bundle())

    assert len(result.accepted) == 0
    assert len(result.rejected) == 1
    assert "does not mention" in result.rejected[0].reason


def test_deduplicates_identical_claims_across_multiple_passes(monkeypatch):
    # extraction_passes pools results from several independent LLM calls over the same text --
    # the same real fact surviving more than once should collapse to one accepted claim, not one
    # per pass.
    monkeypatch.setattr(europepmc, "get_record", lambda identifier: _fake_record())
    same_extraction = _extraction(char_interval=lx.data.CharInterval(0, 10), alignment_status=lx.data.AlignmentStatus.MATCH_EXACT)
    duplicate = _extraction(char_interval=lx.data.CharInterval(0, 10), alignment_status=lx.data.AlignmentStatus.MATCH_LESSER)
    monkeypatch.setattr(lx, "extract", lambda **kwargs: _fake_document([same_extraction, duplicate]))

    result = extract_paper_langextract("pmid:34897256", crop="wheat", api_key="fake", bundle=toy_bundle())

    assert len(result.accepted) == 1


def test_handles_no_text_available(monkeypatch):
    monkeypatch.setattr(europepmc, "get_record", lambda identifier: _fake_record(abstractText=None))
    result = extract_paper_langextract("pmid:34897256", crop="wheat", api_key="fake", bundle=toy_bundle())
    assert result.accepted == []
    assert "no abstract or full text" in result.rejected[0].reason
