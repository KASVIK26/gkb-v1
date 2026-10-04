"""curator/graph/publish.py -- the crosswalk, data dictionary and dataset metadata are generated, so they must agree with the graph and the models."""

from __future__ import annotations

import json

from curator.graph.publish import CROSSWALK_COLUMNS, crosswalk_rows, crosswalk_tsv, data_dictionary_markdown, dataset_metadata
from curator.model.enums import ClaimType
from tests.test_kg_files import _production_bundle


def test_the_crosswalk_has_one_row_per_id_and_the_columns_the_other_products_fill_in():
    bundle = _production_bundle()
    rows = crosswalk_rows(bundle)
    ids = [r["kg_id"] for r in rows]
    assert len(ids) == len(set(ids)) and "dis:wheat:stripe_rust" in ids and "var:wheat:HD2967" in ids
    stripe = next(r for r in rows if r["kg_id"] == "dis:wheat:stripe_rust")
    assert "yellow rust" in stripe["report_abbreviations"]
    assert all(r["phenomic_model_label"] == r["iot_label"] == r["mobile_app_label"] == "" for r in rows)       # for the other teams to fill in, never guessed here
    assert crosswalk_tsv(bundle).splitlines()[0].split("\t") == CROSSWALK_COLUMNS


def test_the_data_dictionary_covers_every_claim_type_and_the_scoring_policy():
    text = data_dictionary_markdown()
    for ctype in ClaimType:
        assert f"### {ctype.value}" in text
    assert "official_document" in text and "Tiers: A >= 0.85" in text


def test_the_dataset_metadata_states_the_cc_by_licence_and_notes_the_split_from_the_code_licence():
    meta = dataset_metadata(_production_bundle(), release="test")
    assert meta["@type"] == "Dataset" and meta["version"] == "test"
    assert meta["license"] == "https://creativecommons.org/licenses/by/4.0/"
    assert "MIT" in meta["licenseNote"] and "CC BY" in meta["licenseNote"]
    json.dumps(meta)
