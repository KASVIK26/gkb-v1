"""Tests for api/routers/lit.py -- extract_paper/assess_source mocked; DB is a real throwaway
Postgres (reuses tests/conftest.py's pg_conn fixture) so the staging read/write path is exercised
for real, not mocked away. No live network or LLM calls."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.deps import get_db, get_llm_client
from api.main import app
from curator.extract.normalize import RejectedCandidate
from curator.graph import staging
from curator.lit import europepmc
from curator.lit.run_extraction import AcceptedCandidate, ExtractionResult
from curator.llm.source_assessment import SourceAssessment
from curator.model.claims import Claim, Evidence, Source
from curator.model.enums import EvidenceMethod, SourceType


@pytest.fixture()
def staging_conn(pg_conn):
    staging.ensure_staging_schema(pg_conn)
    yield pg_conn
    pg_conn.execute("TRUNCATE staging.pending_claim, staging.pending_source CASCADE")


@pytest.fixture()
def client(staging_conn):
    app.dependency_overrides[get_db] = lambda: staging_conn
    app.dependency_overrides[get_llm_client] = lambda: object()  # never actually called; extract_paper is mocked
    yield TestClient(app)
    app.dependency_overrides.clear()


def _fake_result() -> ExtractionResult:
    source = Source(
        id="pmid:34897256", type=SourceType.PUBLICATION, title="A test paper",
        year=2021, venue="Test Journal", verified=True,
    )
    claim = Claim(
        type="GENE_CONFERS_RESISTANCE",
        subject_id="gene:wheat:TestYr1",
        object_id="dis:wheat:stripe_rust",
        qualifiers={"resistance_type": "unknown"},
    )
    evidence = Evidence(
        claim_id=claim.id, source_id=source.id, method=EvidenceMethod.REVIEW_STATEMENT,
        extractor="llm:test-model@claim_extraction_v1", locator="abstract",
        quote="TestYr1 confers resistance to stripe rust in this exact sentence here.",
    )
    return ExtractionResult(
        source=source,
        accepted=[AcceptedCandidate(claim=claim, evidence=evidence, grounding_score=97.5)],
        rejected=[RejectedCandidate(reason="quote does not mention: something", raw={})],
    )


def test_extract_stages_accepted_candidates_and_returns_both_lists(client):
    with patch("api.routers.lit.extract_paper", return_value=_fake_result()), \
         patch("api.routers.lit.europepmc.fetch_abstract", return_value="An abstract about wheat."), \
         patch("api.routers.lit.assess_source", return_value=SourceAssessment(relevant=True, notes="Looks relevant.")):
        response = client.post("/lit/extract", json={"identifier": "pmid:34897256", "crop": "wheat"})

    assert response.status_code == 200
    body = response.json()
    assert body["source_id"] == "pmid:34897256"
    assert body["source_verified"] is True
    assert body["source_assessment"] == {"relevant": True, "notes": "Looks relevant."}
    assert len(body["accepted"]) == 1
    accepted = body["accepted"][0]
    assert accepted["subject_id"] == "gene:wheat:TestYr1"
    assert accepted["grounding_score"] == 97.5
    assert accepted["method_weight"] == pytest.approx(0.35)
    assert accepted["staged_id"] > 0
    assert len(body["rejected"]) == 1
    assert "does not mention" in body["rejected"][0]["reason"]


def test_extract_returns_404_for_unverifiable_paper(client):
    with patch("api.routers.lit.extract_paper", side_effect=europepmc.PublicationNotFound("pmid:1")):
        response = client.post("/lit/extract", json={"identifier": "pmid:1", "crop": "wheat"})
    assert response.status_code == 404


def test_extract_survives_source_assessment_failure(client):
    with patch("api.routers.lit.extract_paper", return_value=_fake_result()), \
         patch("api.routers.lit.europepmc.fetch_abstract", side_effect=RuntimeError("boom")):
        response = client.post("/lit/extract", json={"identifier": "pmid:34897256", "crop": "wheat"})
    assert response.status_code == 200
    assert response.json()["source_assessment"] is None
    assert len(response.json()["accepted"]) == 1  # staging still happened


def test_pending_list_approve_reject_roundtrip(client):
    with patch("api.routers.lit.extract_paper", return_value=_fake_result()), \
         patch("api.routers.lit.europepmc.fetch_abstract", return_value="abstract"), \
         patch("api.routers.lit.assess_source", return_value=SourceAssessment(relevant=True, notes="ok")):
        extract_response = client.post("/lit/extract", json={"identifier": "pmid:34897256", "crop": "wheat"})
    staged_id = extract_response.json()["accepted"][0]["staged_id"]

    pending = client.get("/lit/pending").json()
    assert len(pending) == 1
    assert pending[0]["id"] == staged_id
    assert pending[0]["source_title"] == "A test paper"
    assert pending[0]["method_weight"] == pytest.approx(0.35)

    approve_response = client.post(f"/lit/pending/{staged_id}/approve", json={"reviewer": "vikas"})
    assert approve_response.status_code == 200

    still_pending = client.get("/lit/pending").json()
    assert still_pending == []

    approved = client.get("/lit/pending?status=approved").json()
    assert len(approved) == 1
    assert approved[0]["status"] == "approved"


def test_reject_requires_a_reason(client):
    with patch("api.routers.lit.extract_paper", return_value=_fake_result()), \
         patch("api.routers.lit.europepmc.fetch_abstract", return_value="abstract"), \
         patch("api.routers.lit.assess_source", return_value=SourceAssessment(relevant=True, notes="ok")):
        extract_response = client.post("/lit/extract", json={"identifier": "pmid:34897256", "crop": "wheat"})
    staged_id = extract_response.json()["accepted"][0]["staged_id"]

    missing_reason = client.post(f"/lit/pending/{staged_id}/reject", json={"reviewer": "vikas"})
    assert missing_reason.status_code == 422

    rejected = client.post(
        f"/lit/pending/{staged_id}/reject", json={"reviewer": "vikas", "reason": "not convincing"}
    )
    assert rejected.status_code == 200
    assert client.get("/lit/pending").json() == []
