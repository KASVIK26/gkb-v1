"""Synthetic toy KG for schema and CQ tests.

EVERYTHING HERE IS FAKE. Names use a TEST prefix so the data can never be mistaken for
real knowledge. Only the disease and pathogen IDs are real vocabulary IDs, and the
facts attached to them are invented to exercise specific query paths.

Scenario (wheat):
  zones        TESTZ1 (TESTV1, TESTV2), TESTZ2 (TESTV3)
  TESTV1       stripe rust S (loc A, 2023) and R (loc B, 2024)       -> conflict (CQ10)
  TESTV2       stripe rust MS, leaf rust R, powdery mildew MR         -> donor for 2 diseases (CQ8)
  TESTV3       stripe rust R vs pathotype PT1, S vs PT2              -> NOT a conflict (race-specific)
               leaf rust R; powdery mildew S but REJECTED            -> powdery mildew is a gap (CQ11)
  genes        TestYr1 (TESTV1, TESTV2), TestLr1 (TESTV2)
  TestYr1      defeated by PT2 in 2021; PT2 prevalent in TESTZ1 2022-2023; PT1 prevalent 2010
  TESTQ1       QTL for stripe rust containing TESTLOC1 (NLR) and TESTLOC2
  markers      TESTM1 diagnostic for TestYr1, TESTM2 at 3.2 cM
  trigger      TESTTRIG1 for stripe rust
"""

from __future__ import annotations

from curator.graph.bundle import KGBundle
from curator.model import Claim, ClaimStatus, Entity, Evidence, EvidenceMethod, Source

STRIPE = "dis:wheat:stripe_rust"
LEAF = "dis:wheat:leaf_rust"
MILDEW = "dis:wheat:powdery_mildew"
PST = "path:puccinia_striiformis_f_sp_tritici"
PT1 = f"pt:{PST.split(':')[1]}:TESTPT1"
PT2 = f"pt:{PST.split(':')[1]}:TESTPT2"
Z1, Z2 = "zone:wheat:TESTZ1", "zone:wheat:TESTZ2"
V1, V2, V3 = "var:wheat:TESTV1", "var:wheat:TESTV2", "var:wheat:TESTV3"
YR1, LR1 = "gene:wheat:TestYr1", "gene:wheat:TestLr1"
Q1 = "qtl:wheat:TESTQ1"
LOC1, LOC2 = "ref:wheat:TESTLOC1", "ref:wheat:TESTLOC2"
M1, M2 = "mk:wheat:TESTM1", "mk:wheat:TESTM2"
TRIG = "env:wheat:TESTTRIG1"
SRC = "test:toy1"


def _entities() -> list[Entity]:
    wheat = {"crop": "wheat"}
    ref = {"assembly": "TEST_ASSEMBLY", "chromosome": "2B", "strand": "+"}
    return [
        Entity(id="crop:wheat", type="Crop", name="Wheat", crop="wheat"),
        Entity(id=STRIPE, type="Disease", name="Stripe rust", synonyms=["yellow rust"], **wheat),
        Entity(id=LEAF, type="Disease", name="Leaf rust", **wheat),
        Entity(id=MILDEW, type="Disease", name="Powdery mildew", **wheat),
        Entity(id=PST, type="Pathogen", name="Puccinia striiformis f. sp. tritici"),
        Entity(id=PT1, type="Pathotype", name="TESTPT1", props={"designation": "TESTPT1"}),
        Entity(id=PT2, type="Pathotype", name="TESTPT2", props={"designation": "TESTPT2"}),
        Entity(id=Z1, type="AgroZone", name="Test zone 1", props={"system": "AICRP"}, **wheat),
        Entity(id=Z2, type="AgroZone", name="Test zone 2", props={"system": "AICRP"}, **wheat),
        Entity(id=V1, type="Variety", name="TESTV1", **wheat),
        Entity(id=V2, type="Variety", name="TESTV2", **wheat),
        Entity(id=V3, type="Variety", name="TESTV3", **wheat),
        Entity(id=YR1, type="Gene", name="TestYr1", props={"symbol": "TestYr1", "chromosome": "2B"}, **wheat),
        Entity(id=LR1, type="Gene", name="TestLr1", props={"symbol": "TestLr1"}, **wheat),
        Entity(id=Q1, type="QTL", name="TESTQ1", props={"trait": "stripe rust severity", "chromosome": "2B"}, **wheat),
        Entity(id=LOC1, type="RefGene", name="TESTLOC1",
               props={**ref, "locus_id": "TESTLOC1", "start_bp": 100, "end_bp": 900, "is_nlr": True,
                      "nlr_class": "CNL"}, **wheat),
        Entity(id=LOC2, type="RefGene", name="TESTLOC2",
               props={**ref, "locus_id": "TESTLOC2", "start_bp": 1000, "end_bp": 1800}, **wheat),
        Entity(id=M1, type="Marker", name="TESTM1", props={"marker_type": "KASP"}, **wheat),
        Entity(id=M2, type="Marker", name="TESTM2", props={"marker_type": "SSR"}, **wheat),
        Entity(id=TRIG, type="EnvTrigger", name="TEST stripe rust infection window",
               props={"phase": "infection", "bbch_from": 13, "bbch_to": 75,
                      "conditions": [
                          {"variable": "air_temp_c", "min": 7, "max": 15, "aggregation": "mean", "window_h": 24},
                          {"variable": "est_leaf_wet_h", "min": 3, "aggregation": "sum", "window_h": 24},
                      ]}, **wheat),
    ]


def _reaction(variety: str, disease: str, reaction: str, **extra) -> Claim:
    status = extra.pop("status", ClaimStatus.UNREVIEWED)
    return Claim(type="VARIETY_REACTION", subject_id=variety, object_id=disease, status=status,
                 qualifiers={"reaction": reaction, "stage": "adult", **extra})


def _claims() -> list[Claim]:
    return [
        Claim(type="DISEASE_CAUSED_BY", subject_id=STRIPE, object_id=PST),
        Claim(type="PATHOTYPE_VARIANT_OF", subject_id=PT1, object_id=PST),
        Claim(type="PATHOTYPE_VARIANT_OF", subject_id=PT2, object_id=PST),
        Claim(type="VARIETY_RECOMMENDED_FOR_ZONE", subject_id=V1, object_id=Z1, qualifiers={"season": "rabi"}),
        Claim(type="VARIETY_RECOMMENDED_FOR_ZONE", subject_id=V2, object_id=Z1, qualifiers={"season": "rabi"}),
        Claim(type="VARIETY_RECOMMENDED_FOR_ZONE", subject_id=V3, object_id=Z2, qualifiers={"season": "rabi"}),
        _reaction(V1, STRIPE, "S", location="TEST-A", season="2023"),
        _reaction(V1, STRIPE, "R", location="TEST-B", season="2024"),
        _reaction(V2, STRIPE, "MS"),
        _reaction(V2, LEAF, "R"),
        _reaction(V2, MILDEW, "MR"),
        _reaction(V3, STRIPE, "R", pathotype_id=PT1),
        _reaction(V3, STRIPE, "S", pathotype_id=PT2),
        _reaction(V3, LEAF, "R"),
        _reaction(V3, MILDEW, "S", status=ClaimStatus.REJECTED),
        Claim(type="VARIETY_CARRIES_GENE", subject_id=V1, object_id=YR1, qualifiers={"method": "marker"}),
        Claim(type="VARIETY_CARRIES_GENE", subject_id=V2, object_id=YR1, qualifiers={"method": "pedigree"}),
        Claim(type="VARIETY_CARRIES_GENE", subject_id=V2, object_id=LR1, qualifiers={"method": "marker"}),
        Claim(type="GENE_CONFERS_RESISTANCE", subject_id=YR1, object_id=STRIPE, qualifiers={"resistance_type": "ASR"}),
        Claim(type="GENE_PATHOTYPE_INTERACTION", subject_id=YR1, object_id=PT2,
              qualifiers={"outcome": "defeated", "year": 2021, "region": "TEST region"}),
        Claim(type="PATHOTYPE_PREVALENCE", subject_id=PT2, object_id=Z1, qualifiers={"years": [2022, 2023]}),
        Claim(type="PATHOTYPE_PREVALENCE", subject_id=PT1, object_id=Z1, qualifiers={"years": [2010]}),
        Claim(type="QTL_ASSOCIATION", subject_id=Q1, object_id=STRIPE,
              qualifiers={"lod": 12.5, "pve_pct": 30.0, "population": "TEST RIL"}),
        Claim(type="QTL_CONTAINS_REFGENE", subject_id=Q1, object_id=LOC1, qualifiers={"assembly": "TEST_ASSEMBLY"}),
        Claim(type="QTL_CONTAINS_REFGENE", subject_id=Q1, object_id=LOC2, qualifiers={"assembly": "TEST_ASSEMBLY"}),
        Claim(type="MARKER_LINKAGE", subject_id=M2, object_id=YR1, qualifiers={"distance_cm": 3.2}),
        Claim(type="MARKER_LINKAGE", subject_id=M1, object_id=YR1, qualifiers={"diagnostic": True}),
        Claim(type="DISEASE_ENV_TRIGGER", subject_id=STRIPE, object_id=TRIG),
    ]


def toy_bundle() -> KGBundle:
    claims = _claims()
    evidence = [
        Evidence(claim_id=c.id, source_id=SRC, method=EvidenceMethod.CURATOR_ASSERTION, extractor="manual:test",
                 quote="TEST quote for the trigger claim" if c.type.value == "DISEASE_ENV_TRIGGER" else None)
        for c in claims
    ]
    source = Source(id=SRC, type="test", title="Synthetic toy data for tests")
    return KGBundle(entities=_entities(), sources=[source], claims=claims, evidence=evidence)
