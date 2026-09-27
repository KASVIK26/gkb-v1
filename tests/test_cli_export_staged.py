"""Tests for `agrihub lit export-staged` -- exercised against a real throwaway Postgres (reuses
tests/conftest.py's pg_conn fixture), not mocked, since the whole point is the staging-table ->
YAML -> kg build round trip."""

from __future__ import annotations

import yaml
from typer.testing import CliRunner

from curator.cli import app
from curator.graph import staging
from curator.model.claims import Claim, Evidence, Source
from curator.model.enums import EvidenceMethod, SourceType

runner = CliRunner()


def _seed_one_approved_claim(conn) -> int:
    staging.ensure_staging_schema(conn)
    source = Source(
        id="pmid:34897256", type=SourceType.PUBLICATION, title="A test paper",
        year=2021, venue="Test Journal", verified=True,
    )
    staging.insert_pending_source(conn, source)
    claim = Claim(
        type="GENE_CONFERS_RESISTANCE", subject_id="gene:wheat:TestYr1", object_id="dis:wheat:stripe_rust",
        qualifiers={"resistance_type": "unknown"},
    )
    evidence = Evidence(
        claim_id=claim.id, source_id=source.id, method=EvidenceMethod.REVIEW_STATEMENT,
        extractor="llm:test-model@claim_extraction_v1", locator="abstract",
        quote="TestYr1 confers resistance to stripe rust in this exact sentence here.",
    )
    staged_id = staging.insert_pending_claim(
        conn, claim=claim, evidence=evidence, llm_model="test-model", grounding_score=97.5, source_relevance=None
    )
    staging.approve_pending(conn, staged_id, reviewer="test-reviewer")
    return staged_id


def test_export_staged_writes_yaml_and_marks_exported(pg_conn, pg_dsn, tmp_path):
    staged_id = _seed_one_approved_claim(pg_conn)
    out_path = tmp_path / "pending_test.yaml"

    result = runner.invoke(app, ["lit", "export-staged", "--out", str(out_path), "--database-url", pg_dsn])

    assert result.exit_code == 0, result.output
    assert "Exported 1 approved claim(s)" in result.output
    assert out_path.exists()

    doc = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    assert doc["sources"][0]["id"] == "pmid:34897256"
    assert doc["sources"][0]["verified"] is True
    assert doc["claims"][0]["type"] == "GENE_CONFERS_RESISTANCE"
    assert doc["claims"][0]["subject"] == "gene:wheat:TestYr1"
    assert doc["claims"][0]["evidence"][0]["quote"].startswith("TestYr1 confers resistance")

    rows = staging.list_pending(pg_conn, status="exported")
    assert len(rows) == 1
    assert rows[0]["id"] == staged_id

    pg_conn.execute("TRUNCATE staging.pending_claim, staging.pending_source CASCADE")


def test_export_staged_with_nothing_approved(pg_conn, pg_dsn, tmp_path):
    staging.ensure_staging_schema(pg_conn)
    out_path = tmp_path / "pending_empty.yaml"

    result = runner.invoke(app, ["lit", "export-staged", "--out", str(out_path), "--database-url", pg_dsn])

    assert result.exit_code == 0
    assert "No approved staged claims" in result.output
    assert not out_path.exists()
