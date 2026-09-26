"""Turn config/sources/notified_varieties.yaml (sourced research) into a KGBundle: Variety and
AgroZone entities, VARIETY_RECOMMENDED_FOR_ZONE claims, and VARIETY_REACTION claims (via
resistance_text.py's reviewed phrase lookup).

Scope simplification, documented here rather than left implicit: this project's actual region of
interest (docs/scope.md) is Madhya Pradesh (primary) and Maharashtra (secondary), not the full
AICRP zone definitions (Central Zone spans 5 states for wheat; the Peninsular Zone covers
Karnataka too; chickpea's "Central Zone" definition even includes Maharashtra, unlike wheat's).
Rather than build a full national zone ontology this project doesn't need yet, every variety is
linked to state-level AgroZone entities (zone:<crop>:MP, zone:<crop>:MH) -- one pair per crop,
since a "zone" is crop-scoped in this schema. A variety is only linked to a state if that state is
actually named in its source-document area of adoption (or, for the state-released chickpea
tables and the MP/Maharashtra wheat zone tables, by which table it appears in) -- never inferred
from the breeding institute's location. JGK 6, for example, was bred at JNKVV Jabalpur (MP) but
its official area of adoption is NWPZ states only, so it gets no MP zone claim.

Confidence handling: `tier` in the source file becomes the Evidence method, which is what the
Phase 9 confidence formula (RESEARCH_ROADMAP.md §4.4) actually uses -- not an exclusion filter.
official_document -> EvidenceMethod.OFFICIAL_DOCUMENT (weight 0.90); multi_source_corroborated
and single_source both -> EvidenceMethod.REVIEW_STATEMENT (weight 0.35, the lowest available;
the `tier`/`note` distinction between them remains visible in the loaded claim's source data for
a human reviewer, since the enum has no finer grade below "review statement").
"""

from __future__ import annotations

from pathlib import Path

import yaml

from curator.graph.bundle import KGBundle
from curator.graph.resistance_text import reaction_claims_for
from curator.model import Claim, Entity, Evidence, Source
from curator.normalize.ids import variety_id

SOURCES_DIR = Path(__file__).resolve().parents[2] / "config" / "sources"
VARIETIES_PATH = SOURCES_DIR / "notified_varieties.yaml"

STATES = ("MP", "MH")

_SOURCE_BY_CROP = {
    "wheat": Source(
        id="doc:iiwbr_wheat_varieties_notified",
        type="official_document",
        title="Wheat Varieties Notified in India Since 1965",
        venue="ICAR-Indian Institute of Wheat & Barley Research, Karnal",
        url="https://www.aicrpwheatbarleyicar.in/wp-content/uploads/2021/06/wheat-varieties-notified-in-india.pdf",
        verified=True,
    ),
    "chickpea": Source(
        id="doc:dpd_chickpea_varieties",
        type="official_document",
        title="Central & State Released Varieties - Chickpea (Gram/Chana)",
        venue="Directorate of Pulses Development, Bhopal",
        url="https://dpd.gov.in/i)%20Chickpea%20Varieties.pdf",
        verified=True,
    ),
    "soybean": Source(
        id="doc:dod_soybean_varieties",
        type="official_document",
        title="Soybean varieties for Madhya Pradesh / Maharashtra (district recommendations)",
        venue="Directorate of Oilseeds Development, Hyderabad, and cross-checked search sources",
        url="https://oilseeds.dac.gov.in/Soyabean.aspx",
        verified=True,
    ),
}

_EVIDENCE_METHOD_BY_TIER = {
    "official_document": "official_document",
    "multi_source_corroborated": "review_statement",
    "single_source": "review_statement",
}


def _states_for_entry(crop: str, section: str, v: dict) -> list[str]:
    """Which state-level zones (of MP, MH) this variety should be linked to.

    Wheat's `central_zone` table is a single-state-implicit table -- every row in it was recommended
    for the (5-state) wheat Central Zone, which is state-uniform from this project's point of view
    (MP is the state we care about; the table carries no per-row area-of-adoption text to parse).
    Chickpea's `central_zone` table is different: DPD's own table mixes several states' worth of
    area-of-adoption text into ONE row (e.g. "CZ (MP, CG, MH, GJ)"), so it must be parsed per row --
    that's also why a JNKVV Jabalpur (MP-bred) variety can correctly end up with NO MP zone claim if
    MP isn't actually named in its area of adoption (see the module docstring, JGK 6 example).
    """
    if section in ("madhya_pradesh_state", "madhya_pradesh"):
        return ["MP"]
    if section in ("maharashtra_state", "maharashtra"):
        return ["MH"]
    if section == "central_zone":
        if crop == "wheat":
            return ["MP"]
        area = v.get("area_of_adoption") or ""
        return [s for s in STATES if s in area]
    if section == "peninsular_zone":
        return ["MH"]
    raise ValueError(f"unknown region section {section!r} for {crop}")


def variety_bundle(path: Path = VARIETIES_PATH) -> KGBundle:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))

    entities: dict[str, Entity] = {
        f"zone:{crop}:{state}": Entity(
            id=f"zone:{crop}:{state}", type="AgroZone", name=f"{state} ({crop})", crop=crop,
            props={"system": "state", "states": [state]},
        )
        for crop in ("wheat", "soybean", "chickpea")
        for state in STATES
    }
    sources = list(_SOURCE_BY_CROP.values())
    claims: list[Claim] = []
    evidence: list[Evidence] = []

    for crop in ("wheat", "soybean", "chickpea"):
        crop_data = data[crop]
        source_id = _SOURCE_BY_CROP[crop].id
        for section, entries in crop_data.items():
            if section == "source_document":
                continue
            for v in entries:
                vid = variety_id(crop, v["name"])
                if vid not in entities:
                    synonyms = [v["common_name"]] if v.get("common_name") else []
                    entities[vid] = Entity(
                        id=vid, type="Variety", name=v["name"], crop=crop, synonyms=synonyms,
                        props={
                            "release_year": v.get("year"),
                            "releasing_institute": v.get("institute"),
                        },
                    )

                method = _EVIDENCE_METHOD_BY_TIER[v["tier"]]
                locator = v.get("notification") or v.get("area_of_adoption") or section

                for state in _states_for_entry(crop, section, v):
                    zone_claim = Claim(
                        type="VARIETY_RECOMMENDED_FOR_ZONE", subject_id=vid,
                        object_id=f"zone:{crop}:{state}",
                    )
                    claims.append(zone_claim)
                    evidence.append(Evidence(
                        claim_id=zone_claim.id, source_id=source_id, method=method,
                        extractor="manual:curator", locator=locator,
                    ))

                for disease_id, reaction, stage in reaction_claims_for(crop, v.get("resistance")):
                    reaction_claim = Claim(
                        type="VARIETY_REACTION", subject_id=vid, object_id=disease_id,
                        qualifiers={"reaction": reaction.value, "stage": stage.value},
                    )
                    claims.append(reaction_claim)
                    evidence.append(Evidence(
                        claim_id=reaction_claim.id, source_id=source_id, method=method,
                        extractor="manual:curator", locator=v["name"], quote=v.get("resistance"),
                    ))

    return KGBundle(entities=list(entities.values()), sources=sources, claims=claims, evidence=evidence)
