"""Consistency checks for config/sources/notified_varieties.yaml.

Schema v2: each crop has a `source_document` plus one or more region sections (each a list of
variety dicts), rather than one flat `varieties` list -- MP and Maharashtra are both covered now
for wheat and chickpea.
"""

from pathlib import Path

import pytest
import yaml

SOURCES_DIR = Path(__file__).resolve().parents[1] / "config" / "sources"
VALID_TIERS = {"official_document", "multi_source_corroborated", "single_source"}
CROPS = ("wheat", "soybean", "chickpea")


@pytest.fixture(scope="module")
def data() -> dict:
    return yaml.safe_load((SOURCES_DIR / "notified_varieties.yaml").read_text(encoding="utf-8"))


def _region_sections(data: dict, crop: str) -> dict[str, list[dict]]:
    return {k: v for k, v in data[crop].items() if k != "source_document" and isinstance(v, list)}


def _all_varieties(data: dict, crop: str):
    for section, entries in _region_sections(data, crop).items():
        for v in entries:
            yield section, v


@pytest.mark.parametrize("crop", CROPS)
def test_every_crop_has_a_source_document_and_at_least_one_region(data, crop):
    assert data[crop]["source_document"].get("title")
    sections = _region_sections(data, crop)
    assert sections, f"{crop} has no region sections"
    assert sum(len(v) for v in sections.values()) > 0


@pytest.mark.parametrize("crop", CROPS)
def test_every_variety_has_required_fields_and_a_valid_tier(data, crop):
    for section, v in _all_varieties(data, crop):
        assert v.get("name"), (crop, section, v)
        assert v.get("institute"), (crop, section, v["name"])
        assert v["tier"] in VALID_TIERS, (crop, section, v["name"], v["tier"])
        assert v.get("institute_is_mp") is not None or v.get("institute_is_mh") is not None, (
            crop, section, v["name"],
        )


@pytest.mark.parametrize("crop", CROPS)
def test_variety_names_are_unique_within_a_region_section(data, crop):
    for section, entries in _region_sections(data, crop).items():
        names = [v["name"] for v in entries]
        assert len(names) == len(set(names)), f"duplicate names in {crop}.{section}: {names}"


def test_official_document_entries_carry_a_notification_or_area_reference(data):
    """The strongest tier should point at something checkable: a gazette notification number
    (wheat/some chickpea) or at least the area-of-adoption line from the source table
    (chickpea central-zone entries don't all carry a bare notification number in the source)."""
    for crop in CROPS:
        for section, v in _all_varieties(data, crop):
            if v["tier"] == "official_document":
                assert v.get("notification") or v.get("area_of_adoption") or v.get("note"), (
                    crop, section, v["name"],
                )


def test_missing_release_years_are_explicitly_noted(data):
    for crop in CROPS:
        for section, v in _all_varieties(data, crop):
            if v.get("year") is None:
                assert v.get("note"), (crop, section, v["name"])


def test_wheat_has_both_regions_with_deep_official_coverage():
    data_ = yaml.safe_load((SOURCES_DIR / "notified_varieties.yaml").read_text(encoding="utf-8"))
    cz = data_["wheat"]["central_zone"]
    pz = data_["wheat"]["peninsular_zone"]
    assert sum(1 for v in cz if v["institute_is_mp"]) >= 15
    assert sum(1 for v in pz if v["tier"] == "official_document") >= 15


def test_chickpea_covers_both_mp_and_maharashtra_with_official_tier():
    data_ = yaml.safe_load((SOURCES_DIR / "notified_varieties.yaml").read_text(encoding="utf-8"))
    mp = data_["chickpea"]["madhya_pradesh_state"]
    mh = data_["chickpea"]["maharashtra_state"]
    assert sum(1 for v in mp if v["tier"] == "official_document") >= 8
    assert sum(1 for v in mh if v["tier"] == "official_document") >= 8


def test_rvg_202_conflict_is_documented_not_silently_resolved():
    """This is the one known conflicting-evidence case surfaced during research -- make sure it
    stays visible rather than getting quietly cleaned up in a future edit."""
    data_ = yaml.safe_load((SOURCES_DIR / "notified_varieties.yaml").read_text(encoding="utf-8"))
    rvg202 = next(v for v in data_["chickpea"]["central_zone"] if "RVG 202" in v.get("common_name", ""))
    assert "CONFLICTING" in rvg202["note"]
