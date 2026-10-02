"""Materialise Crop / Disease / Pathogen reference entities from config/vocab/diseases.yaml.

These are NOT hand-curated per release. config/vocab/diseases.yaml (docs/scope.md) is the single
source of truth for the 17 in-scope disease IDs; every build regenerates the corresponding
entities and a cheap DISEASE_CAUSED_BY claim from it, so a hand-curated file only ever needs to
*reference* a disease ID (e.g. "dis:wheat:stem_rust"), never redefine it.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from curator.graph.bundle import KGBundle
from curator.model import Claim, Entity, Evidence, EvidenceMethod, Source
from curator.model.enums import Crop
from curator.normalize.ids import slugify

VOCAB_DIR = Path(__file__).resolve().parents[2] / "config" / "vocab"
VOCAB_SOURCE_ID = "vocab:diseases_yaml"


def reference_bundle(path: Path = VOCAB_DIR / "diseases.yaml") -> KGBundle:
    vocab = yaml.safe_load(path.read_text(encoding="utf-8"))
    entities: dict[str, Entity] = {
        f"crop:{crop.value}": Entity(id=f"crop:{crop.value}", type="Crop", name=crop.value.capitalize(), crop=crop)
        for crop in Crop
    }
    claims: list[Claim] = []
    evidence: list[Evidence] = []

    zones_path = path.parent / "aicrp_zones.yaml"
    if zones_path.exists():
        for z in yaml.safe_load(zones_path.read_text(encoding="utf-8"))["zones"]:
            entities[z["id"]] = Entity(
                id=z["id"], type="AgroZone", name=f"{z['name']} ({z['crop']})", crop=z["crop"],
                synonyms=[z["name"], z["abbreviation"]],
                props={"system": "AICRP", "states": z["states"], "definition": z["definition"],
                       "definition_source": z["definition_source"]},
            )

    for d in vocab["diseases"]:
        entities[d["id"]] = Entity(
            id=d["id"],
            type="Disease",
            name=d["name"],
            crop=d["crop"],
            synonyms=d.get("synonyms", []),
            props={"group": d["group"]} if d.get("group") else {},
        )

        pathogen_name = d.get("pathogen")
        if not pathogen_name:
            continue
        pathogen_id = f"path:{slugify(pathogen_name)}"
        if pathogen_id not in entities:
            props = {}
            if d.get("pathogen_type"):
                props["pathogen_type"] = d["pathogen_type"]
            entities[pathogen_id] = Entity(
                id=pathogen_id, type="Pathogen", name=pathogen_name,
                synonyms=d.get("pathogen_synonyms", []), props=props,
            )

        claim = Claim(type="DISEASE_CAUSED_BY", subject_id=d["id"], object_id=pathogen_id)
        claims.append(claim)
        evidence.append(
            Evidence(
                claim_id=claim.id,
                source_id=VOCAB_SOURCE_ID,
                method=EvidenceMethod.CURATOR_ASSERTION,
                extractor="manual:curator",
                locator=f"config/vocab/diseases.yaml#{d['id']}",
            )
        )

    source = Source(
        id=VOCAB_SOURCE_ID,
        type="curated_vocab",
        title="AgriHub GKB disease/pathogen vocabulary (docs/scope.md)",
        verified=True,
    )
    return KGBundle(entities=list(entities.values()), sources=[source], claims=claims, evidence=evidence)
