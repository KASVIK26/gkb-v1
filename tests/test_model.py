"""Unit tests for the KG v2 model, ID rules, synonyms and release gates (no database)."""

from __future__ import annotations

import pytest
from kg_toy import SRC, STRIPE, V1, YR1, toy_bundle
from pydantic import ValidationError

from curator.graph.bundle import KGBundle
from curator.model import Claim, Entity, Evidence, EvidenceMethod, Source
from curator.model.enums import CLAIM_SIGNATURE, ClaimType
from curator.model.claims import QUALIFIERS
from curator.normalize.ids import (
    InvalidId, gene_id, lookup_key, parse_id, slugify, validate_chromosome, variety_id,
)
from curator.normalize.synonyms import AmbiguousName, SynonymIndex


# ─────────────────────────── IDs ───────────────────────────
@pytest.mark.parametrize(
    ("crop", "name", "expected"),
    [
        ("wheat", "HD 3086", "var:wheat:HD3086"),
        ("soybean", "JS 95-60", "var:soybean:JS9560"),
        ("chickpea", "Pusa Chickpea 20211", "var:chickpea:PUSACHICKPEA20211"),
    ],
)
def test_variety_ids(crop, name, expected):
    assert variety_id(crop, name) == expected


def test_gene_ids_keep_case():
    assert gene_id("wheat", "Lr 34") == "gene:wheat:Lr34"
    assert gene_id("soybean", "rhg1") == "gene:soybean:rhg1"  # recessive: lowercase is meaningful
    assert gene_id("soybean", "Rhg4") != gene_id("soybean", "rhg4")


@pytest.mark.parametrize(
    "bad", ["var:maize:X1", "gene:wheat:", "foo:wheat:X", "path:Puccinia", "pt:missing_designation", "crop:rice"]
)
def test_invalid_ids_rejected(bad):
    with pytest.raises(InvalidId):
        parse_id(bad)


def test_slug_and_lookup_key():
    assert slugify("Puccinia striiformis f. sp. tritici") == "puccinia_striiformis_f_sp_tritici"
    assert lookup_key("HD-3086") == lookup_key("hd 3086") == "hd3086"


@pytest.mark.parametrize(
    ("crop", "chromosome", "ok"),
    [
        ("wheat", "3AL", True), ("wheat", "1D", True), ("wheat", "9B", False), ("wheat", "8A", False),
        ("soybean", "Gm18", True), ("soybean", "18", True), ("soybean", "Gm21", False),
        ("chickpea", "Ca2", True), ("chickpea", "CaLG4", True), ("chickpea", "Ca9", False),
    ],
)
def test_chromosome_validation(crop, chromosome, ok):
    if ok:
        assert validate_chromosome(crop, chromosome) == chromosome
    else:
        with pytest.raises(ValueError):
            validate_chromosome(crop, chromosome)


# ─────────────────────────── synonyms ───────────────────────────
def test_disease_synonyms_resolve():
    index = SynonymIndex.from_disease_vocab()
    assert index.resolve("Yellow Rust") == "dis:wheat:stripe_rust"
    assert index.resolve("head scab") == "dis:wheat:fusarium_head_blight"
    assert index.resolve("rust", crop="chickpea") == "dis:chickpea:rust"
    with pytest.raises(AmbiguousName):
        index.resolve("rust")
    assert index.resolve("unknown disease") is None


def test_gene_synonyms_collapse_to_one_entity():
    index = SynonymIndex()
    index.add("gene:wheat:Lr34", "Lr34", "Yr18", "Sr57", "Pm38")
    assert {index.resolve(n) for n in ("Yr 18", "sr57", "PM38")} == {"gene:wheat:Lr34"}


# ─────────────────────────── entities ───────────────────────────
def test_entity_id_must_match_type_and_crop():
    with pytest.raises(ValidationError, match="is a Gene"):
        Entity(id="gene:wheat:Sr31", type="Variety", name="x", crop="wheat")
    with pytest.raises(ValidationError, match="does not match"):
        Entity(id="gene:wheat:Sr31", type="Gene", name="Sr31", crop="soybean", props={"symbol": "Sr31"})


def test_entity_rejects_impossible_chromosome():
    with pytest.raises(ValidationError, match="not a valid wheat chromosome"):
        Entity(id="gene:wheat:Sr35", type="Gene", name="Sr35", crop="wheat",
               props={"symbol": "Sr35", "chromosome": "9B"})


def test_entity_props_are_strict():
    with pytest.raises(ValidationError):
        Entity(id="gene:wheat:X1", type="Gene", name="X1", crop="wheat", props={"symbol": "X1", "confidnce": "High"})


def test_env_trigger_variables_must_come_from_sensor_vocab():
    base = {"phase": "infection", "bbch_from": 10, "bbch_to": 20}
    with pytest.raises(ValidationError, match="sensors.yaml"):
        Entity(id="env:wheat:T1", type="EnvTrigger", name="t", crop="wheat",
               props={**base, "conditions": [{"variable": "leaf_wetness_h", "min": 3, "aggregation": "sum",
                                               "window_h": 24}]})
    Entity(id="env:wheat:T1", type="EnvTrigger", name="t", crop="wheat",
           props={**base, "conditions": [{"variable": "rh_ge_90_h", "min": 6, "aggregation": "sum",
                                           "window_h": 24}]})


# ─────────────────────────── claims & evidence ───────────────────────────
def test_every_claim_type_has_signature_and_qualifiers():
    assert set(CLAIM_SIGNATURE) == set(ClaimType) == set(QUALIFIERS)


def test_claim_signature_enforced():
    with pytest.raises(ValidationError, match="subject must be"):
        Claim(type="VARIETY_REACTION", subject_id=YR1, object_id=STRIPE,
              qualifiers={"reaction": "S", "stage": "adult"})


def test_claim_qualifiers_validated_and_id_is_content_based():
    a = Claim(type="VARIETY_REACTION", subject_id=V1, object_id=STRIPE,
              qualifiers={"reaction": "S", "stage": "adult", "location": None})
    b = Claim(type="VARIETY_REACTION", subject_id=V1, object_id=STRIPE,
              qualifiers={"stage": "adult", "reaction": "S"})
    c = Claim(type="VARIETY_REACTION", subject_id=V1, object_id=STRIPE,
              qualifiers={"stage": "adult", "reaction": "R"})
    assert a.id == b.id != c.id
    with pytest.raises(ValidationError):
        Claim(type="VARIETY_REACTION", subject_id=V1, object_id=STRIPE,
              qualifiers={"reaction": "very bad", "stage": "adult"})


def test_llm_evidence_requires_quote():
    claim_id = toy_bundle().claims[0].id
    with pytest.raises(ValidationError, match="verbatim quote"):
        Evidence(claim_id=claim_id, source_id=SRC, method=EvidenceMethod.REVIEW_STATEMENT,
                 extractor="llm:some-model@prompt-v1")
    Evidence(claim_id=claim_id, source_id=SRC, method=EvidenceMethod.REVIEW_STATEMENT,
             extractor="llm:some-model@prompt-v1", quote="HD3086 showed a susceptible reaction at Indore")


def test_source_ids_must_fit_type():
    with pytest.raises(ValidationError):
        Source(id="pmid:PMC123", type="publication", title="x")
    with pytest.raises(ValidationError):
        Source(id="doi:10.1/x", type="dataset", title="x")
    Source(id="pmid:37480228", type="publication", title="x")


# ─────────────────────────── release gates ───────────────────────────
def test_toy_bundle_passes_gates_only_when_test_sources_allowed():
    bundle = toy_bundle()
    assert bundle.gate_errors(allow_test_sources=True) == []
    assert any("test source" in e for e in bundle.gate_errors())


def test_gates_catch_unsupported_claims_and_unverified_publications():
    bundle = toy_bundle()
    orphan = Claim(type="VARIETY_CARRIES_GENE", subject_id=V1, object_id=YR1, qualifiers={"method": "stated"})
    unverified = Source(id="pmid:1", type="publication", title="unverified paper")
    ev = Evidence(claim_id=bundle.claims[0].id, source_id=unverified.id, method=EvidenceMethod.GWAS,
                  extractor="manual:test")
    broken = KGBundle(entities=bundle.entities, sources=[*bundle.sources, unverified],
                      claims=[*bundle.claims, orphan], evidence=[*bundle.evidence, ev])
    errors = broken.gate_errors(allow_test_sources=True)
    assert any("has no evidence" in e for e in errors)
    assert any("not verified" in e for e in errors)
