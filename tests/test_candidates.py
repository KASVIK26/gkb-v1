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
    assert "Candidate ingest report" in report_markdown(result)


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
    # an Sr gene acts on the stem rust pathogen, so the new pathotype's pathogen is known from the claim itself ...
    assert _run(bundle, base, text=text).counts() == {"accepted": 1}
    # ... but a gene whose symbol names no pathogen class gives no such default
    unknown_class = {**base, "subject": {"text": "Rpp1", "type": "Gene"}, "quote": "Sr31 was defeated by pathotype TKTTF in Ethiopia."}
    assert _run(bundle, unknown_class, text=text.replace("Sr31", "Rpp1")).counts() != {"accepted": 1}
    good = {**base, "object": {"text": "TKTTF", "type": "Pathotype", "props": {"pathogen": "path:puccinia_graminis_f_sp_tritici"}}}
    result = _run(bundle, good, text=text)
    assert result.counts() == {"accepted": 1}
    assert "pt:puccinia_graminis_f_sp_tritici:TKTTF" in result.entities


def test_aicrp_zone_by_name_or_abbreviation_and_the_quote_must_name_it(bundle):
    text = PAPER_TEXT + " HI 1544 is recommended for the Central Zone under timely sown irrigated conditions."
    base = _candidate(claim_type="VARIETY_RECOMMENDED_FOR_ZONE", subject={"text": "HI 1544", "type": "Variety"},
                      object={"text": "Central Zone", "type": "AgroZone"}, qualifiers={"sowing": "timely", "water_regime": "irrigated"},
                      quote="HI 1544 is recommended for the Central Zone under timely sown irrigated conditions.", evidence_basis="primary_field")
    result = _run(bundle, base, text=text)
    assert result.counts() == {"accepted": 1}
    (spec,) = result.claims.values()
    assert spec["object"] == "zone:wheat:CZ"
    # "CZ" resolves to the same zone, and the quote names it by one of its accepted names
    assert _run(bundle, {**base, "object": {"text": "CZ", "type": "AgroZone"}}, text=text).counts() == {"accepted": 1}
    # a zone of ANOTHER crop is a different entity: wheat has no "Southern Zone"
    assert _run(bundle, {**base, "object": {"text": "Southern Zone", "type": "AgroZone"}}, text=text).counts() == {"rejected": 1}


def test_reviewer_can_name_the_entity_when_two_lookup_keys_collide(bundle):
    """"MAUS 612" and "MAUS 61-2" (Pratishta) share the key maus612, so neither resolves by text; the override is explicit."""
    text = PAPER_TEXT + " MAUS 61-2 was recommended for the Madhya Pradesh region in 2002."
    base = _candidate(claim_type="VARIETY_RECOMMENDED_FOR_ZONE", subject={"text": "MAUS 61-2", "type": "Variety"},
                      object={"text": "MP", "type": "AgroZone"}, qualifiers={}, quote="MAUS 61-2 was recommended for the Madhya Pradesh region in 2002.",
                      evidence_basis="official_document", crop="soybean",
                      source={"kind": "official_document", "url": "https://example.gov.in/s.html", "doc_slug": "example_soy", "title": "Soybean varieties"})
    assert _run(bundle, base, text=text, url_text=text).counts() != {"accepted": 1}
    pinned = {**base, "subject": {"text": "MAUS 61-2", "type": "Variety", "entity_id": "var:soybean:PRATISHTA"}}
    result = _run(bundle, pinned, text=text, url_text=text)
    assert result.counts() == {"accepted": 1}
    assert next(iter(result.claims.values()))["subject"] == "var:soybean:PRATISHTA"
    wrong_type = {**base, "subject": {"text": "x", "type": "Variety", "entity_id": "dis:soybean:rust"}}
    assert _run(bundle, wrong_type, text=text, url_text=text).counts() == {"rejected": 1}


def test_a_new_variety_keeps_its_common_name_as_a_synonym(bundle):
    text = PAPER_TEXT + " The variety Brandnew 77 (Pusa Testwala) was resistant to leaf rust."
    cand = _candidate(subject={"text": "Brandnew 77", "type": "Variety", "synonyms": ["Pusa Testwala"]}, qualifiers={"reaction": "R", "stage": "adult"},
                      quote="The variety Brandnew 77 (Pusa Testwala) was resistant to leaf rust.")
    result = _run(bundle, cand, text=text)
    assert result.entities["var:wheat:BRANDNEW77"].synonyms == ["Pusa Testwala"]


def test_pinning_works_even_when_the_pinned_entitys_own_name_collides(bundle):
    """var:soybean:MAUS612 shares its lookup key with Pratishta's synonym "MAUS 61-2": text resolution is ambiguous, the id is not."""
    text = PAPER_TEXT + " MAUS 612 was recommended for Maharashtra in 2018."
    base = _candidate(claim_type="VARIETY_RECOMMENDED_FOR_ZONE", subject={"text": "MAUS 612", "type": "Variety"}, object={"text": "MH", "type": "AgroZone"},
                      qualifiers={}, quote="MAUS 612 was recommended for Maharashtra in 2018.", evidence_basis="official_document", crop="soybean",
                      source={"kind": "official_document", "url": "https://example.gov.in/s.html", "doc_slug": "example_soy", "title": "Soybean varieties"})
    assert _run(bundle, base, text=text, url_text=text).counts() != {"accepted": 1}
    pinned = {**base, "subject": {"text": "MAUS 612", "type": "Variety", "entity_id": "var:soybean:MAUS612"}}
    result = _run(bundle, pinned, text=text, url_text=text)
    assert result.counts() == {"accepted": 1} and next(iter(result.claims.values()))["subject"] == "var:soybean:MAUS612"


def test_an_en_dash_name_resolves_to_the_existing_variety(bundle):
    text = PAPER_TEXT + " RVS 2001–4 stayed resistant to soybean rust."
    cand = _candidate(crop="soybean", subject={"text": "RVS 2001–4", "type": "Variety"}, object={"text": "Soybean rust", "type": "Disease"},
                      qualifiers={"reaction": "R", "stage": "unspecified"}, quote="RVS 2001–4 stayed resistant to soybean rust.")
    result = _run(bundle, cand, text=text)
    claims = list(result.claims.values())
    assert claims and claims[0]["subject"] == "var:soybean:RVS20014" and not result.entities


def test_an_extra_key_in_the_source_block_is_ignored_but_not_elsewhere(bundle):
    ok = _candidate(source={"kind": "publication", "pmid": "99999001", "title": "Leaf rust reactions of Indian wheat varieties", "primary": True})
    assert _run(bundle, ok).counts() == {"accepted": 1}
    typo = _candidate(qualifiers={"reaction": "MR", "stage": "adult", "locaton": "Indore"})
    assert _run(bundle, typo).counts() == {"rejected": 1}


def test_a_new_qtl_for_a_disease_gets_that_disease_as_its_trait_but_a_marker_still_needs_its_type(bundle):
    text = PAPER_TEXT + " MQTL1A.1 flanked by Glu-A3 and Xgwm136 is associated with leaf rust resistance (LOD 5.2)."
    cand = _candidate(claim_type="QTL_ASSOCIATION", subject={"text": "MQTL1A.1", "type": "QTL"}, object={"text": "leaf rust", "type": "Disease"},
                      qualifiers={"lod": 5.2}, quote="MQTL1A.1 flanked by Glu-A3 and Xgwm136 is associated with leaf rust resistance (LOD 5.2).", evidence_basis="primary_qtl")
    result = _run(bundle, cand, text=text)
    assert result.counts() == {"accepted": 1}
    assert result.entities["qtl:wheat:MQTL1A.1"].props["trait"] == "leaf rust resistance"


# ---------- papers Europe PMC does not index: Crossref fallback ----------
WORK = {"DOI": "10.18805/lr-9999", "title": ["Screening of chickpea genotypes against Fusarium wilt"], "issued": {"date-parts": [[2021]]},
        "container-title": ["Legume Research"]}


def _doi_candidate(**over):
    return _candidate(source={"kind": "publication", "doi": "10.18805/LR-9999", "title": "Screening of chickpea genotypes against Fusarium wilt"},
                      quote="HI 1544 stayed moderately resistant to leaf rust.", **over)


def _run_doi(bundle, work, page_text):
    def fetch_record(identifier):
        raise europepmc.PublicationNotFound(identifier)
    return process_candidates([json.dumps(_doi_candidate())], bundle=bundle, fetch_record=fetch_record, fetch_text=lambda _i: None,
                              fetch_url=lambda _u: page_text, fetch_work=lambda _d: work)


def test_a_doi_unknown_to_europe_pmc_is_verified_through_crossref_and_the_publisher_page(bundle):
    result = _run_doi(bundle, WORK, PAPER_TEXT)
    assert result.counts() == {"accepted": 1}
    source = result.sources["doi:10.18805/lr-9999"]
    assert source.verified and source.venue == "Legume Research" and source.year == 2021


def test_a_quote_not_on_the_publishers_page_is_unverifiable_not_rejected(bundle):
    result = _run_doi(bundle, WORK, "Abstract only. " * 400)        # the page is readable but the quote lives in the PDF we cannot read
    assert result.counts() == {"unverifiable": 1}


def test_crossref_title_mismatch_and_unregistered_doi_are_rejected(bundle):
    assert _run_doi(bundle, {**WORK, "title": ["A completely unrelated paper on maize silage"]}, PAPER_TEXT).counts() == {"rejected": 1}
    assert _run_doi(bundle, None, PAPER_TEXT).counts() == {"rejected": 1}


# ---------- pathotypes and shared advisories ----------
def test_a_new_pathotype_takes_its_pathogen_from_the_claim(bundle):
    text = PAPER_TEXT + " Pathotype 238S119 is a variant of Puccinia striiformis f. sp. tritici."
    cand = _candidate(claim_type="PATHOTYPE_VARIANT_OF", subject={"text": "238S119", "type": "Pathotype"},
                      object={"text": "Puccinia striiformis f. sp. tritici", "type": "Pathogen"}, qualifiers={},
                      quote="Pathotype 238S119 is a variant of Puccinia striiformis f. sp. tritici.", evidence_basis="official_document",
                      source={"kind": "official_document", "url": "https://example.gov.in/p.pdf", "doc_slug": "example_path", "title": "Pathotypes"})
    result = _run(bundle, cand, text=text, url_text=text)
    assert result.counts() == {"accepted": 1}
    assert "pt:puccinia_striiformis_f_sp_tritici:238S119" in result.entities


def test_one_advisory_can_manage_several_diseases_without_colliding(bundle):
    text = "For rust control spray Propiconazole 25 EC at 0.1% on wheat against yellow rust and leaf rust. " + "x " * 2000
    adv = {"text": "Propiconazole spray", "type": "Advisory",
           "advisory": {"action_type": "chemical", "active_ingredient": "Propiconazole 25 EC", "dose": "0.1%"}}
    base = _candidate(claim_type="DISEASE_MANAGED_BY", qualifiers={}, object=adv, evidence_basis="review_or_secondary",
                      quote="spray Propiconazole 25 EC at 0.1% on wheat against yellow rust and leaf rust")
    two = [json.dumps({**base, "candidate_id": "A1", "subject": {"text": "yellow rust", "type": "Disease"}}),
           json.dumps({**base, "candidate_id": "A2", "subject": {"text": "leaf rust", "type": "Disease"}})]
    result = process_candidates(two, bundle=bundle, fetch_record=lambda _i: RECORD, fetch_text=lambda _i: text, fetch_url=lambda _u: None)
    assert result.counts() == {"accepted": 2}
    advisories = [e for e in result.entities.values() if e.type.value == "Advisory"]
    assert len(advisories) == 1                                    # one practice ...
    assert len({spec["subject"] for spec in result.claims.values()}) == 2   # ... managing two diseases


def test_pathotype_with_a_slash_gets_a_safe_id_and_keeps_its_printed_name(bundle):
    text = PAPER_TEXT + " Among 302 brown rust isolates, pathotypes 52-4 and 52/77-9 together constituted two-thirds of the population."
    cand = _candidate(claim_type="PATHOTYPE_VARIANT_OF", subject={"text": "52/77-9", "type": "Pathotype"},
                      object={"text": "Puccinia triticina", "type": "Pathogen", "alias_in_quote": "brown rust"}, qualifiers={},
                      quote="Among 302 brown rust isolates, pathotypes 52-4 and 52/77-9 together constituted two-thirds of the population.",
                      evidence_basis="official_document",
                      source={"kind": "official_document", "url": "https://example.gov.in/m.pdf", "doc_slug": "example_mehta", "title": "Mehtaensis"})
    result = _run(bundle, cand, text=text, url_text=text)
    assert result.counts() == {"accepted": 1}
    assert result.entities["pt:puccinia_triticina:52_77-9"].name == "52/77-9"


def test_a_decoded_dose_is_accepted_when_its_numbers_are_in_the_quote_and_refused_when_one_is_not(bundle):
    text = "Propiconazole 25% EC ... Wheat ... Stripe rust 125gm 500gm 750 30 " + "x " * 2000
    def cand(dose):
        return _candidate(claim_type="DISEASE_MANAGED_BY", qualifiers={}, subject={"text": "stripe rust", "type": "Disease"}, evidence_basis="official_document",
                          object={"text": "Propiconazole 25% EC spray", "type": "Advisory", "advisory": {"action_type": "chemical", "active_ingredient": "Propiconazole 25% EC", "dose": dose}},
                          quote="Propiconazole 25% EC ... Wheat ... Stripe rust 125gm 500gm 750 30",
                          source={"kind": "official_document", "url": "https://example.gov.in/c.pdf", "doc_slug": "example_cibrc", "title": "CIBRC"})
    ok = _run(bundle, cand("125gm a.i. and 500gm formulation per ha in 750 l water"), text=text, url_text=text)
    assert ok.counts() == {"accepted": 1}
    bad = _run(bundle, cand("150gm a.i. and 500gm formulation per ha in 750 l water"), text=text, url_text=text)
    assert bad.counts() == {"needs_review": 1} and "150" in bad.outcomes[0].reason
