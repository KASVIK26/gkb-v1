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


def load_records(driver: Any, records: list[dict[str, Any]]) -> None:
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
