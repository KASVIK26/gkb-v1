"""Load curated records into Neo4j using idempotent MERGE statements."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LoaderConfig:
    uri: str
    user: str
    password: str


def build_load_query() -> str:
    return """
    MERGE (g:Gene {id: $gene.id})
      SET g.chromosome = $gene.chromosome,
          g.allele = $gene.allele,
          g.resistance_type = $gene.resistance_type
    MERGE (d:Disease {name: $disease.name})
      SET d.pathogen = $disease.pathogen
    MERGE (t:Treatment {action: $treatment.action, iot_trigger: $treatment.iot_trigger})
    MERGE (g)-[r:CONFERS_RESISTANCE_TO]->(d)
      SET r.confidence = $confidence,
          r.source = $source
    MERGE (d)-[:TREATED_BY]->(t)
    """.strip()


def load_records(driver: Any, records: list) -> None:
    """Bulk-load seed records into Neo4j (used by seed_loader.py)."""
    query = build_load_query()
    with driver.session() as session:
        for record in records:
            session.run(
                query,
                gene=record["gene"],
                disease=record["disease"],
                treatment=record.get("treatment", {"action": None, "iot_trigger": None}),
                confidence=record["confidence"],
                source=record["source"],
            )


_EDGE_QUERY = """
MERGE (g:Gene {id: $gene_id})
  ON CREATE SET g.resistance_type = $resistance_type
  ON MATCH SET g.resistance_type = COALESCE(g.resistance_type, $resistance_type)

MERGE (d:Disease {name: $disease_name})
  ON CREATE SET d.pathogen = $pathogen
  ON MATCH SET d.pathogen = COALESCE(d.pathogen, $pathogen)

MERGE (g)-[r:CONFERS_RESISTANCE_TO]->(d)
  SET r.confidence = $confidence, r.source = $source

WITH g, d, $treatment_action AS action, $iot_trigger AS iot
WHERE action IS NOT NULL
MERGE (t:Treatment {action: action, iot_trigger: iot})
MERGE (d)-[:TREATED_BY]->(t)
"""

_VARIETY_QUERY = """
MATCH (g:Gene {id: $gene_id})
MERGE (v:Variety {name: $variety_name, crop: $crop})
MERGE (v)-[:CARRIES {confidence: $confidence}]->(g)
"""


def load_edge_record(driver: Any, record: dict) -> None:
    """Load a single AI-extracted record into Neo4j via idempotent MERGE."""
    gene_id = record["gene"]
    disease_name = record["disease"]
    confidence = record["confidence"]
    source = record["source"]
    pathogen = record.get("pathogen")
    resistance_type = record.get("resistance_type", "unknown")
    treatment_action = record.get("treatment")
    iot_trigger = record.get("iot_trigger")
    varieties = record.get("varieties") or []
    crop = record.get("crop", "unknown")

    with driver.session() as session:
        session.run(
            _EDGE_QUERY,
            gene_id=gene_id,
            disease_name=disease_name,
            pathogen=pathogen,
            resistance_type=resistance_type,
            confidence=confidence,
            source=source,
            treatment_action=treatment_action,
            iot_trigger=iot_trigger,
        )
        for variety_name in varieties:
            if variety_name:
                session.run(
                    _VARIETY_QUERY,
                    gene_id=gene_id,
                    variety_name=variety_name,
                    crop=crop,
                    confidence=confidence,
                )
