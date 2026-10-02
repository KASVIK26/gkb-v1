"""Tests for turning config/sources/notified_varieties.yaml into a KGBundle."""

from __future__ import annotations

import pytest

from curator.graph.bundle import KGBundle
from curator.graph.resistance_text import UnmappedResistanceText, reaction_claims_for
from curator.graph.variety_import import variety_bundle
from curator.graph.vocab_entities import reference_bundle
from curator.model.enums import EntityType
from curator.normalize.ids import variety_id


@pytest.fixture(scope="module")
def bundle() -> KGBundle:
    return variety_bundle()


def _zones(bundle: KGBundle, vid: str) -> set[str]:
    return {c.object_id for c in bundle.claims if c.type.value == "VARIETY_RECOMMENDED_FOR_ZONE" and c.subject_id == vid}


def _reactions(bundle: KGBundle, vid: str) -> set[tuple[str, str]]:
    return {
        (c.object_id, c.qualifiers["reaction"])
        for c in bundle.claims if c.type.value == "VARIETY_REACTION" and c.subject_id == vid
    }


# ─────────────────────────── resistance_text.py ───────────────────────────
def test_every_phrase_in_the_source_file_is_mapped():
    """Guards against the source file being edited with a new phrase that silently gets no
    claim -- this must fail loudly (via variety_bundle()) instead."""
    import yaml

    from curator.graph.variety_import import VARIETIES_PATH

    data = yaml.safe_load(VARIETIES_PATH.read_text(encoding="utf-8"))
    for crop in ("wheat", "soybean", "chickpea"):
        for section, entries in data[crop].items():
            if section == "source_document":
                continue
            for v in entries:
                reaction_claims_for(crop, v.get("resistance"))  # raises if unmapped


def test_unmapped_phrase_raises_instead_of_guessing():
    with pytest.raises(UnmappedResistanceText):
        reaction_claims_for("wheat", "some brand new phrase never reviewed before")


def test_out_of_scope_diseases_never_produce_a_claim():
    """Yellow Mosaic Virus (soybean) is a different virus from Soybean mosaic virus (SMV) and is
    explicitly out of scope -- must never turn into a dis:soybean:mosaic_virus claim."""
    assert reaction_claims_for("soybean", "Resistant to YMV") == []
    ymv_and_rot = reaction_claims_for("soybean", "Resistant to YMV and Charcoal Rot")
    diseases = [d for d, _, _ in ymv_and_rot]
    assert diseases == ["dis:soybean:charcoal_rot"]  # YMV silently dropped, charcoal rot kept


def test_soybean_pod_blight_is_not_guessed_into_a_disease():
    """The DAC page says "Pod blight" with no pathogen; it must not become pod_stem_blight or anthracnose."""
    nrc86 = reaction_claims_for("soybean", "Resistant to bacterial postule, Pod blight, collar rot, girdle beetle and Stem fly")
    assert [d for d, _, _ in nrc86] == ["dis:soybean:bacterial_pustule"]
    seven = reaction_claims_for(
        "soybean", "Resistant YMV, Charcoal Rot, Bacterial Pustules, Alternaria Leaf spot, Pod blight, Indian bud blight, Target leaf spot"
    )
    assert [d for d, _, _ in seven] == ["dis:soybean:charcoal_rot", "dis:soybean:bacterial_pustule"]


def test_withdrawn_soybean_phrases_are_no_longer_reviewed():
    """These were not on the cited DAC page; they must fail loudly if someone puts them back."""
    for phrase in ("reported rust and pest resistant", "moderately resistant to Alternaria leaf spot, bacterial pustule, target leaf spot"):
        with pytest.raises(UnmappedResistanceText):
            reaction_claims_for("soybean", phrase)


def test_tolerant_maps_to_moderately_resistant_not_resistant():
    claims = reaction_claims_for("chickpea", "tolerant to wilt")
    assert claims == [("dis:chickpea:fusarium_wilt", claims[0][1], claims[0][2])]
    assert claims[0][1].value == "MR"


def test_adult_plant_resistance_carries_the_stage():
    claims = reaction_claims_for("wheat", "adult plant resistance to brown and black rust")
    assert {stage.value for _, _, stage in claims} == {"adult"}


# ─────────────────────────── variety_bundle() ───────────────────────────
def test_bundle_passes_release_gates_when_merged_with_reference_entities(bundle):
    merged = KGBundle.merge(reference_bundle(), bundle)
    assert merged.gate_errors() == []


def test_institute_location_is_not_used_to_infer_zone(bundle):
    """JGK 6 was bred at JNKVV Jabalpur (Madhya Pradesh) but its official area of adoption is
    NWPZ states only -- it must get zero MP/MH zone claims, not one inferred from the institute."""
    vid = variety_id("chickpea", "JGK 6")
    assert _zones(bundle, vid) == set()


def test_wheat_central_zone_maps_to_mp_and_peninsular_zone_to_mh(bundle):
    gw322 = variety_id("wheat", "GW 322")
    assert _zones(bundle, gw322) == {"zone:wheat:MP"}
    macs6478 = variety_id("wheat", "MACS 6478")
    assert _zones(bundle, macs6478) == {"zone:wheat:MH"}


def test_chickpea_central_zone_area_of_adoption_is_parsed_per_row(bundle):
    """RVG 202's area of adoption explicitly names both MP and MH -- it should get both zone
    claims, sourced from the row's own text, not assumed."""
    rvg202 = variety_id("chickpea", "Raj Vijay Gram 202")
    assert _zones(bundle, rvg202) == {"zone:chickpea:MP", "zone:chickpea:MH"}


def test_variety_recommended_in_both_states_gets_both_zone_claims(bundle):
    js335 = variety_id("soybean", "JS 335")
    assert _zones(bundle, js335) == {"zone:soybean:MP", "zone:soybean:MH"}


def test_rvg202_conflict_is_preserved_as_moderately_resistant_to_three_diseases(bundle):
    rvg202 = variety_id("chickpea", "Raj Vijay Gram 202")
    assert _reactions(bundle, rvg202) == {
        ("dis:chickpea:fusarium_wilt", "MR"),
        ("dis:chickpea:dry_root_rot", "MR"),
        ("dis:chickpea:collar_rot", "MR"),
    }


def test_same_variety_across_two_sections_is_one_entity_not_two(bundle):
    js335 = variety_id("soybean", "JS 335")
    matches = [e for e in bundle.entities if e.id == js335]
    assert len(matches) == 1


def test_every_variety_entity_is_well_typed(bundle):
    varieties = [e for e in bundle.entities if e.type is EntityType.VARIETY]
    assert len(varieties) > 100
    for e in varieties:
        assert e.crop is not None
        e.typed_props  # raises if props don't validate against VarietyProps


def test_zone_entities_cover_both_states_for_all_three_crops(bundle):
    zones = {e.id for e in bundle.entities if e.type is EntityType.AGRO_ZONE}
    expected = {f"zone:{crop}:{state}" for crop in ("wheat", "soybean", "chickpea") for state in ("MP", "MH")}
    assert zones == expected
