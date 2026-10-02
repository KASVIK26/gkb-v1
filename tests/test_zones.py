"""config/vocab/aicrp_zones.yaml: AICRP zones are vocabulary, so their structure and provenance are checked here.
(That each definition is verbatim in its source is checked by hand against the documents when the file changes.)"""

from __future__ import annotations

import re

import pytest

from curator.graph.bundle import KGBundle
from curator.graph.variety_import import variety_bundle
from curator.graph.vocab_entities import reference_bundle


@pytest.fixture(scope="module")
def bundle() -> KGBundle:
    return KGBundle.merge(reference_bundle(), variety_bundle())


def _aicrp_zones(bundle):
    return [e for e in bundle.entities if e.type.value == "AgroZone" and e.props["system"] == "AICRP"]


def test_each_crop_has_its_aicrp_zones(bundle):
    by_crop = {}
    for z in _aicrp_zones(bundle):
        by_crop.setdefault(z.crop.value, set()).add(z.id.rsplit(":", 1)[1])
    assert by_crop == {
        "wheat": {"NWPZ", "NEPZ", "CZ", "PZ", "NHZ"},
        "soybean": {"NHZ", "NPZ", "CZ", "NEZ", "SZ"},
        "chickpea": {"CZ", "NWPZ", "NEPZ", "SZ", "NHZ"},
    }


def test_every_zone_definition_points_at_a_source_that_is_in_the_kg(bundle):
    source_ids = {s.id for s in bundle.sources}
    for z in _aicrp_zones(bundle):
        assert z.props["definition"].strip()
        assert z.props["definition_source"] in source_ids, z.id
        assert all(re.fullmatch(r"[A-Z]{2}", code) for code in z.props["states"]), z.id


def test_same_named_zones_in_different_crops_do_not_collide(bundle):
    from curator.extract.normalize import resolve_entity_from_bundle
    from curator.model.enums import EntityType

    for crop in ("wheat", "soybean", "chickpea"):
        assert resolve_entity_from_bundle("Central Zone", EntityType.AGRO_ZONE, bundle.entities, crop) == f"zone:{crop}:CZ"
        assert resolve_entity_from_bundle("CZ", EntityType.AGRO_ZONE, bundle.entities, crop) == f"zone:{crop}:CZ"


def test_maharashtra_is_wheat_pz_but_only_part_of_soybean_sz(bundle):
    """Why zones are crop-scoped: the two documents draw the line differently."""
    wheat_pz = next(e for e in bundle.entities if e.id == "zone:wheat:PZ")
    soy_sz = next(e for e in bundle.entities if e.id == "zone:soybean:SZ")
    assert "Maharashtra and Karnataka" == wheat_pz.props["definition"]
    assert "Southern parts of Maharashtra" in soy_sz.props["definition"]


def test_hindi_zone_names_resolve_for_the_soybean_page(bundle):
    from curator.extract.normalize import resolve_entity_from_bundle
    from curator.model.enums import EntityType

    assert resolve_entity_from_bundle("मध्य क्षेत्र", EntityType.AGRO_ZONE, bundle.entities, "soybean") == "zone:soybean:CZ"
    assert resolve_entity_from_bundle("दक्षिण क्षेत्र", EntityType.AGRO_ZONE, bundle.entities, "soybean") == "zone:soybean:SZ"
