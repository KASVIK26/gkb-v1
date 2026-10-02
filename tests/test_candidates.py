"""curator/lit/candidates.py -- external (ChatGPT/Grok) claim candidates are verified, never trusted.

The registry and the text fetchers are faked, so these tests need no network."""

from __future__ import annotations

import json

import pytest
import yaml

from curator.graph.bundle import KGBundle
from curator.graph.kg_files import load_curated_file
from curator.graph.variety_import import variety_bundle
from curator.graph.vocab_entities import reference_bundle
from curator.lit import europepmc
from curator.lit.candidates import process_candidates, report_markdown, to_curated_yaml

PAPER_TEXT = (
    "Methods. Field trials were run at Indore in two seasons. Results. The wheat variety Brandnew 77 was "
    "highly resistant to leaf rust at the adult stage in all locations. HI 1544 stayed moderately resistant to leaf rust."
 + " Further discussion follows." * 150
)
RECORD = {"pmid": "99999001", "doi": "10.1000/test", "title": "Leaf rust reactions of Indian wheat varieties.",
          "pubYear": "2024", "journalTitle": "Test Journal", "pubTypeList": {"pubType": ["Journal Article"]}}


@pytest.fixture(scope="module")
def bundle() -> KGBundle:
    return KGBundle.merge(reference_bundle(), variety_bundle())


def _candidate(**overrides) -> dict:
    base = {
        "candidate_id": "T-1", "producer": "chatgpt-deep-research", "batch_id": "wo-test", "crop": "wheat",
        "claim_type": "VARIETY_REACTION",
        "subject": {"text": "HI 1544", "type": "Variety"}, "object": {"text": "leaf rust", "type": "Disease"},
        "qualifiers": {"reaction": "MR", "stage": "adult"},
        "source": {"kind": "publication", "pmid": "99999001", "title": "Leaf rust reactions of Indian wheat varieties"},
        "locator": "full text, Results",
        "quote": "HI 1544 stayed moderately resistant to leaf rust.",
        "evidence_basis": "primary_field",
    }
    base.update(overrides)
    return base


def _run(bundle, *candidates, record=RECORD, text=PAPER_TEXT, url_text=None):
    def fetch_record(identifier):
        if record is None:
            raise europepmc.PublicationNotFound(identifier)
        return record

    return process_candidates(
        [json.dumps(c) for c in candidates], bundle=bundle,
        fetch_record=fetch_record, fetch_text=lambda _id: text, fetch_url=lambda _url: url_text,
    )


def test_a_verified_candidate_becomes_a_claim_with_registry_metadata(bundle):
    result = _run(bundle, _candidate(quote="HI 1544 stayed moderately resistant to leaf rust."))
    assert result.counts() == {"accepted": 1}
    source = result.sources["pmid:99999001"]
    assert source.verified and source.title == "Leaf rust reactions of Indian wheat varieties"
    (spec,) = result.claims.values()
    evidence = spec["evidence"][0]
    assert evidence["method"] == "field_single_env"
    assert evidence["extractor"].startswith("llm:chatgpt-deep-research@")


def test_title_the_model_invented_is_rejected(bundle):
    result = _run(bundle, _candidate(source={"kind": "publication", "pmid": "99999001", "title": "A completely different paper about maize"}))
    assert result.counts() == {"rejected": 1}
    assert "title mismatch" in result.outcomes[0].reason


def test_unknown_pmid_is_rejected(bundle):
    result = _run(bundle, _candidate(), record=None)
    assert result.counts() == {"rejected": 1}
    assert "not found on Europe PMC" in result.outcomes[0].reason


def test_paraphrased_quote_is_rejected(bundle):
    result = _run(bundle, _candidate(quote="The cultivar HI 1544 showed good tolerance towards brown rust in trials."))
    assert result.counts() == {"rejected": 1}
    assert "quote not found" in result.outcomes[0].reason


def test_unreadable_source_is_unverifiable_not_accepted(bundle):
    result = _run(bundle, _candidate(), text=None)
    assert result.counts() == {"unverifiable": 1}


def test_unknown_disease_is_rejected_and_counted_as_a_missing_entity(bundle):
    result = _run(bundle, _candidate(object={"text": "zebra stripe disease", "type": "Disease"}, quote="HI 1544 stayed moderately resistant to leaf rust."))
    assert result.counts() == {"rejected": 1}
    assert result.missing_entities["Disease: zebra stripe disease"] == 1


def test_new_variety_is_created_when_nothing_similar_exists(bundle):
    result = _run(bundle, _candidate(subject={"text": "Brandnew 77", "type": "Variety"},
                                     qualifiers={"reaction": "R", "stage": "adult"},
                                     quote="the wheat variety Brandnew 77 was highly resistant to leaf rust at the adult stage"))
    assert result.counts() == {"accepted": 1}
    assert "var:wheat:BRANDNEW77" in result.entities


def test_near_duplicate_of_an_existing_variety_goes_to_a_person(bundle):
    # "MACS 40280" is an extra digit on the existing MACS 4028: a typo or a new variety, not our call.
    result = _run(bundle, _candidate(subject={"text": "MACS 40280", "type": "Variety"}, quote="HI 1544 stayed moderately resistant to leaf rust."))
    assert result.counts() == {"needs_review": 1}
    assert "very close to existing" in result.outcomes[0].reason


def test_quote_that_does_not_name_the_variety_goes_to_a_person(bundle):
    result = _run(bundle, _candidate(quote="Field trials were run at Indore in two seasons."))
    assert result.counts() == {"needs_review": 1}
    assert "does not name the subject" in result.outcomes[0].reason


def test_a_review_article_can_only_be_review_statement(bundle):
    review = {**RECORD, "pubTypeList": {"pubType": ["Review", "Journal Article"]}}
    result = _run(bundle, _candidate(), record=review)
    (spec,) = result.claims.values()
    assert spec["evidence"][0]["method"] == "review_statement"


def test_primary_field_with_two_locations_is_multi_environment(bundle):
    result = _run(bundle, _candidate(qualifiers={"reaction": "MR", "stage": "adult", "n_locations": 3}))
    (spec,) = result.claims.values()
    assert spec["evidence"][0]["method"] == "field_multi_env"


def test_invalid_qualifier_and_bad_lines_are_rejected_not_fatal(bundle):
    result = process_candidates(
        ["not json at all", json.dumps(_candidate(candidate_id="T-2", qualifiers={"reaction": "SUPER-R", "stage": "adult"}))],
        bundle=bundle, fetch_record=lambda _i: RECORD, fetch_text=lambda _i: PAPER_TEXT, fetch_url=lambda _u: None,
    )
    assert result.counts() == {"rejected": 2}


def test_official_document_must_be_readable_at_its_url(bundle):
    doc = _candidate(
        source={"kind": "official_document", "url": "https://example.gov.in/list.pdf", "doc_slug": "example_list_2024", "title": "Notified varieties 2024", "publisher": "Example Directorate"},
        evidence_basis="official_document", quote="HI 1544 stayed moderately resistant to leaf rust.")
    ok = _run(bundle, doc, url_text=PAPER_TEXT)
    assert ok.counts() == {"accepted": 1} and "doc:example_list_2024" in ok.sources
    assert _run(bundle, doc, url_text=None).counts() == {"unverifiable": 1}


def test_advisory_is_created_from_a_structured_block_and_dose_must_be_in_the_quote(bundle):
    text = "For yellow rust control spray Propiconazole 25 EC at 0.1% when the disease is first noticed."
    advisory = {"text": "Propiconazole spray at first appearance", "type": "Advisory",
                "advisory": {"action_type": "chemical", "active_ingredient": "Propiconazole 25 EC", "dose": "0.1%", "timing": "when the disease is first noticed"}}
    good = _run(bundle, _candidate(claim_type="DISEASE_MANAGED_BY", qualifiers={}, subject={"text": "yellow rust", "type": "Disease"}, object=advisory,
                                   quote="For yellow rust control spray Propiconazole 25 EC at 0.1% when the disease is first noticed", evidence_basis="review_or_secondary"), text=text)
    assert good.counts() == {"accepted": 1}
    assert any(e.type.value == "Advisory" for e in good.entities.values())
    wrong_dose = {**advisory, "advisory": {**advisory["advisory"], "dose": "5%"}}
    flagged = _run(bundle, _candidate(claim_type="DISEASE_MANAGED_BY", qualifiers={}, subject={"text": "yellow rust", "type": "Disease"}, object=wrong_dose,
                                      quote="For yellow rust control spray Propiconazole 25 EC at 0.1% when the disease is first noticed", evidence_basis="review_or_secondary"), text=text)
    assert flagged.counts() == {"needs_review": 1}
    assert "dose" in flagged.outcomes[0].reason


def test_written_yaml_loads_and_passes_the_release_gates_with_the_reference_data(bundle, tmp_path):
    result = _run(bundle, _candidate(subject={"text": "Brandnew 77", "type": "Variety"}, qualifiers={"reaction": "R", "stage": "adult"},
                                     quote="the wheat variety Brandnew 77 was highly resistant to leaf rust at the adult stage"))
    path = tmp_path / "batch.yaml"
    path.write_text(to_curated_yaml(result, "test batch"), encoding="utf-8")
    loaded = load_curated_file(path)
    merged = KGBundle.merge(bundle, loaded)
    assert merged.gate_errors() == []
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["claims"][0]["evidence"][0]["extractor"].startswith("llm:")
    assert "Candidate ingest report" in report_markdown(result, sample=["T-1"])


def test_alias_used_in_the_quote_is_accepted_and_recorded(bundle):
    text = PAPER_TEXT + " Plots of Brandnew 77 showed LR severity of 5%."
    candidate = _candidate(subject={"text": "Brandnew 77", "type": "Variety"}, object={"text": "leaf rust", "type": "Disease", "alias_in_quote": "LR"},
                           qualifiers={"reaction": "R", "stage": "adult"}, quote="Plots of Brandnew 77 showed LR severity of 5%.")
    result = _run(bundle, candidate, text=text)
    assert result.counts() == {"accepted": 1}
    (spec,) = result.claims.values()
    assert "alias in quote" in spec["evidence"][0]["locator"]
    without = {**candidate, "object": {"text": "leaf rust", "type": "Disease"}}
    assert _run(bundle, without, text=text).counts() == {"needs_review": 1}


def test_zone_claim_resolves_a_state_code_and_the_quote_must_name_the_state(bundle):
    text = PAPER_TEXT + " HI 1544 is recommended for timely sown irrigated conditions in Madhya Pradesh."
    candidate = _candidate(claim_type="VARIETY_RECOMMENDED_FOR_ZONE", subject={"text": "HI 1544", "type": "Variety"},
                           object={"text": "MP", "type": "AgroZone"}, qualifiers={"season": "rabi", "sowing": "timely", "water_regime": "irrigated"},
                           quote="HI 1544 is recommended for timely sown irrigated conditions in Madhya Pradesh.", evidence_basis="official_document",
                           source={"kind": "official_document", "url": "https://example.gov.in/z.pdf", "doc_slug": "example_zone_list", "title": "Zone list"})
    result = _run(bundle, candidate, text=text, url_text=text)
    assert result.counts() == {"accepted": 1}
    assert _run(bundle, {**candidate, "object": {"text": "Gujarat", "type": "AgroZone"}}, text=text, url_text=text).counts() == {"rejected": 1}


def test_new_marker_and_qtl_need_the_properties_the_model_requires(bundle):
    text = PAPER_TEXT + " The marker Xgwm533 is linked to Sr2 in Brandnew 77."
    base = _candidate(claim_type="MARKER_LINKAGE", subject={"text": "Xgwm533", "type": "Marker"}, object={"text": "Sr2", "type": "Gene"},
                      qualifiers={"distance_cm": 1.2}, quote="The marker Xgwm533 is linked to Sr2 in Brandnew 77.", evidence_basis="primary_marker")
    assert _run(bundle, base, text=text).counts() == {"rejected": 1}  # no marker_type given
    with_type = {**base, "subject": {"text": "Xgwm533", "type": "Marker", "props": {"marker_type": "SSR"}}}
    result = _run(bundle, with_type, text=text)
    assert result.counts() == {"accepted": 1}
    assert "mk:wheat:Xgwm533" in result.entities and "gene:wheat:Sr2" in result.entities


def test_pathotype_is_created_only_under_an_existing_pathogen(bundle):
    text = PAPER_TEXT + " Sr31 was defeated by pathotype TKTTF in Ethiopia."
    base = _candidate(claim_type="GENE_PATHOTYPE_INTERACTION", subject={"text": "Sr31", "type": "Gene"},
                      object={"text": "TKTTF", "type": "Pathotype"}, qualifiers={"outcome": "defeated"},
                      quote="Sr31 was defeated by pathotype TKTTF in Ethiopia.", evidence_basis="primary_field")
    assert _run(bundle, base, text=text).counts() == {"rejected": 1}
    good = {**base, "object": {"text": "TKTTF", "type": "Pathotype", "props": {"pathogen": "path:puccinia_graminis_f_sp_tritici"}}}
    result = _run(bundle, good, text=text)
    assert result.counts() == {"accepted": 1}
    assert "pt:puccinia_graminis_f_sp_tritici:TKTTF" in result.entities
