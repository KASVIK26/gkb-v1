"""Consistency checks for config/sources/candidate_papers.yaml (the vetted paper bibliography)."""

from pathlib import Path

import pytest
import yaml

VOCAB_DIR = Path(__file__).resolve().parents[1] / "config" / "vocab"
SOURCES_DIR = Path(__file__).resolve().parents[1] / "config" / "sources"
VALID_SOURCE_TYPES = {"peer_reviewed_primary", "peer_reviewed_review", "extension_publication"}
VALID_VERIFIED_VIA = {"europepmc_id", "europepmc_title", "search_result"}


@pytest.fixture(scope="module")
def diseases() -> dict:
    return yaml.safe_load((VOCAB_DIR / "diseases.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def papers() -> dict:
    return yaml.safe_load((SOURCES_DIR / "candidate_papers.yaml").read_text(encoding="utf-8"))


def _all_entries(papers: dict):
    for crop, diseases in papers.items():
        if crop == "schema_version":
            continue
        for disease_id, entries in diseases.items():
            for entry in entries:
                yield disease_id, entry


def test_every_in_scope_disease_has_at_least_one_paper(diseases, papers):
    known_ids = {d["id"] for d in diseases["diseases"]}
    covered = {disease_id for disease_id, _ in _all_entries(papers)}
    assert covered == known_ids, f"missing: {known_ids - covered}, unknown: {covered - known_ids}"


def test_every_entry_is_individually_identifiable(papers):
    """Every entry needs either a pmid, a doi, or (for non-journal sources) a url -- something
    a reader can actually go check, not just a title typed into this file."""
    for disease_id, entry in _all_entries(papers):
        assert entry.get("pmid") or entry.get("doi") or entry.get("url"), (disease_id, entry.get("title"))


def test_every_entry_has_a_title_and_declared_verification_method(papers):
    for disease_id, entry in _all_entries(papers):
        assert entry.get("title"), disease_id
        assert entry["source_type"] in VALID_SOURCE_TYPES, (disease_id, entry["source_type"])
        assert entry["verified_via"] in VALID_VERIFIED_VIA, (disease_id, entry["verified_via"])


def test_non_peer_reviewed_sources_are_not_missing_a_pmid_by_accident(papers):
    """extension_publication entries legitimately have no PMID. Anything claiming to be
    peer-reviewed should have a real identifier (pmid or doi), not just a bare url."""
    for disease_id, entry in _all_entries(papers):
        if entry["source_type"] != "extension_publication":
            assert entry.get("pmid") or entry.get("doi"), (disease_id, entry.get("title"))


def test_weaker_verification_is_explicitly_flagged(papers):
    """search_result-verified entries (no PMID found via Europe PMC) should carry a `note`
    explaining why, so a reader doesn't mistake them for as-solid-as an EXT_ID lookup."""
    for disease_id, entry in _all_entries(papers):
        if entry["verified_via"] == "search_result" and entry["source_type"] != "extension_publication":
            assert entry.get("note"), (disease_id, entry.get("title"))
