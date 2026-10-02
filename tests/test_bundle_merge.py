"""KGBundle.merge: the same claim in two curated files is one claim whose evidence accumulates."""

from __future__ import annotations

from curator.graph.bundle import KGBundle
from curator.model import Claim, Entity, Evidence, EvidenceMethod, Source, SourceType

VARIETY = Entity(id="var:chickpea:TESTV1", type="Variety", name="Test V1", crop="chickpea")
DISEASE = Entity(id="dis:chickpea:fusarium_wilt", type="Disease", name="Fusarium wilt", crop="chickpea")


def _source(n: int) -> Source:
    return Source(id=f"pmid:{n}", type=SourceType.PUBLICATION, title=f"Paper {n}", year=2020, verified=True)


def _claim() -> Claim:
    return Claim(type="VARIETY_REACTION", subject_id=VARIETY.id, object_id=DISEASE.id, qualifiers={"reaction": "R", "stage": "unspecified"})


def _bundle(source_n: int) -> KGBundle:
    claim, source = _claim(), _source(source_n)
    evidence = Evidence(claim_id=claim.id, source_id=source.id, method=EvidenceMethod.FIELD_MULTI_ENV, extractor="manual:test")
    return KGBundle(entities=[VARIETY, DISEASE], sources=[source], claims=[claim], evidence=[evidence])


def test_same_claim_in_two_bundles_is_one_claim_with_both_sources():
    merged = KGBundle.merge(_bundle(1), _bundle(2))
    assert len(merged.claims) == 1
    assert sorted(ev.source_id for ev in merged.evidence) == ["pmid:1", "pmid:2"]
    assert merged.gate_errors() == []


def test_gate_catches_a_duplicated_claim_built_by_hand():
    claim = _claim()
    bundle = KGBundle(entities=[VARIETY, DISEASE], sources=[], claims=[claim, claim], evidence=[])
    assert any("duplicate claim IDs" in error for error in bundle.gate_errors())
