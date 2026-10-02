"""Unit tests for curator/lit/europepmc.py -- everything mocked, no live network calls."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from curator.lit import europepmc


def _mock_json_response(body: dict):
    """Return a context-manager mock whose .read().decode() yields `body` as JSON bytes."""
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(body).encode("utf-8")
    mock_response.__enter__.return_value = mock_response
    mock_response.__exit__.return_value = False
    return mock_response


def _core_result(**overrides) -> dict:
    result = {
        "pmid": "34897256",
        "title": "Characterization of Xanthomonas citri pv. glycines...",
        "journalTitle": "The Plant Pathology Journal",
        "pubYear": "2021",
        "isOpenAccess": "Y",
        "pmcid": "PMC8666981",
        "abstractText": "Bacterial pustule caused by Xanthomonas citri pv. glycines is a major pathogen of soybean.",
    }
    result.update(overrides)
    return {"hitCount": 1, "resultList": {"result": [result]}}


def test_search_appends_open_access_filter():
    with patch("urllib.request.urlopen", return_value=_mock_json_response({"resultList": {"result": []}})) as mock_open:
        europepmc.search("soybean AND rust", open_access_only=True)
        called_url = mock_open.call_args[0][0].full_url
        assert "OPEN_ACCESS%3Ay" in called_url or "OPEN_ACCESS:y" in called_url


def test_search_returns_raw_hits_unmodified():
    hits = [{"pmid": "123", "title": "Some paper"}]
    with patch("urllib.request.urlopen", return_value=_mock_json_response({"resultList": {"result": hits}})):
        results = europepmc.search("wheat AND rust")
    assert results == hits


def test_verify_publication_found():
    with patch("urllib.request.urlopen", return_value=_mock_json_response(_core_result())):
        meta = europepmc.verify_publication("pmid:34897256")

    assert meta.id == "pmid:34897256"
    assert meta.year == 2021
    assert meta.venue == "The Plant Pathology Journal"
    assert meta.is_open_access is True
    assert meta.pmcid == "PMC8666981"


def test_verify_publication_by_doi():
    with patch("urllib.request.urlopen", return_value=_mock_json_response(_core_result())) as mock_open:
        europepmc.verify_publication("doi:10.5423/PPJ.FT.11.2021.0164")
        called_url = mock_open.call_args[0][0].full_url
        assert "DOI" in called_url


def test_verify_publication_not_found_raises():
    with patch("urllib.request.urlopen", return_value=_mock_json_response({"resultList": {"result": []}})):
        with pytest.raises(europepmc.PublicationNotFound):
            europepmc.verify_publication("pmid:99999999999")


def test_verify_publication_rejects_malformed_identifier():
    with pytest.raises(ValueError, match="pmid:<digits>"):
        europepmc.get_record("not-a-real-identifier")


def test_verify_publication_closed_access():
    with patch("urllib.request.urlopen", return_value=_mock_json_response(_core_result(isOpenAccess="N", pmcid=None))):
        meta = europepmc.verify_publication("pmid:34897256")
    assert meta.is_open_access is False
    assert meta.pmcid is None


def test_abstract_from_record():
    record = _core_result()["resultList"]["result"][0]
    assert "Xanthomonas" in europepmc.abstract_from_record(record)


def test_abstract_from_record_missing():
    assert europepmc.abstract_from_record({}) is None


def test_fetch_fulltext_xml_returns_text_on_success():
    mock_response = MagicMock()
    mock_response.read.return_value = b"<article>full text</article>"
    mock_response.__enter__.return_value = mock_response
    mock_response.__exit__.return_value = False
    with patch("urllib.request.urlopen", return_value=mock_response):
        text = europepmc.fetch_fulltext_xml("PMC8666981")
    assert text == "<article>full text</article>"


def test_fetch_fulltext_xml_returns_none_on_404():
    import urllib.error

    with patch("urllib.request.urlopen", side_effect=urllib.error.HTTPError(
        "url", 404, "Not Found", {}, None
    )):
        assert europepmc.fetch_fulltext_xml("PMC0000000") is None


def test_metadata_venue_falls_back_to_journal_info_for_core_records():
    # Europe PMC "core" records often have no journalTitle at all, only journalInfo.journal.title --
    # previously every such paper was verified with venue=None (the review app showed "unknown venue").
    record = {"pmid": "29134790", "title": "A title.", "pubYear": "2018", "isOpenAccess": "N",
              "journalInfo": {"journal": {"title": "Molecular plant pathology"}}}
    assert europepmc.metadata_from_record(record, "pmid:29134790").venue == "Molecular plant pathology"


def test_metadata_prefers_journal_title_and_tolerates_neither():
    base = {"pmid": "1", "title": "T.", "pubYear": "2020", "isOpenAccess": "N"}
    assert europepmc.metadata_from_record({**base, "journalTitle": "J1", "journalInfo": {"journal": {"title": "J2"}}}, "pmid:1").venue == "J1"
    assert europepmc.metadata_from_record(base, "pmid:1").venue is None
