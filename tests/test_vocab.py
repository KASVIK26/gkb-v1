"""Consistency checks for the shared vocabularies in config/vocab/."""

from pathlib import Path

import pytest
import yaml

VOCAB = Path(__file__).resolve().parents[1] / "config" / "vocab"
CROPS = {"wheat", "soybean", "chickpea"}


def _load(name: str) -> dict:
    return yaml.safe_load((VOCAB / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def diseases() -> dict:
    return _load("diseases.yaml")


@pytest.fixture(scope="module")
def stages() -> dict:
    return _load("growth_stages.yaml")


@pytest.fixture(scope="module")
def sensors() -> dict:
    return _load("sensors.yaml")


def test_disease_ids_unique_and_well_formed(diseases):
    ids = [d["id"] for d in diseases["diseases"]]
    assert len(ids) == len(set(ids))
    for d in diseases["diseases"]:
        prefix, crop, slug = d["id"].split(":")
        assert prefix == "dis" and crop == d["crop"] and slug
        assert d["crop"] in CROPS
        assert d["sensor_coupling"] in {"direct", "proxy", "indirect"}


def test_scope_counts(diseases):
    by_crop = {c: sum(d["crop"] == c for d in diseases["diseases"]) for c in CROPS}
    assert by_crop == {"soybean": 8, "wheat": 5, "chickpea": 4}


def test_disease_groups_reference_known_ids(diseases):
    ids = {d["id"] for d in diseases["diseases"]}
    for group in diseases["groups"]:
        assert set(group["members"]) <= ids
        for member in group["members"]:
            assert next(d for d in diseases["diseases"] if d["id"] == member)["group"] == group["id"]


@pytest.mark.parametrize("crop", sorted(CROPS))
def test_stages_cover_sowing_to_harvest_in_order(stages, crop):
    codes = [s["bbch"] for s in stages["crops"][crop]["stages"]]
    assert codes[0] == 0 and codes[-1] == 99
    assert codes == sorted(codes) and len(codes) == len(set(codes))


def test_every_disease_has_a_watch_window(stages, diseases):
    windows = {
        w["disease"]: (crop, w["bbch"])
        for crop, spec in stages["crops"].items()
        for w in spec["watch_windows"]
    }
    for d in diseases["diseases"]:
        assert d["id"] in windows, f"no watch window for {d['id']}"
        crop, (start, end) = windows[d["id"]]
        assert crop == d["crop"] and 0 <= start < end <= 99


def test_sensor_names_unique(sensors):
    names = [v["name"] for section in ("measured", "fused", "derived", "external") for v in sensors[section]]
    assert len(names) == len(set(names))


def test_measured_sources_are_known_hardware(sensors):
    hardware = {h["id"] for h in sensors["hardware"]}
    for var in sensors["measured"]:
        assert var["source"] in hardware
        low, high = var["valid_range"]
        assert low < high
