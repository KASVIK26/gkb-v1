"""Load seed data into Neo4j."""

from __future__ import annotations

from curator.db import DBConfig, DBDriver
from curator.seed_data import SEED_EDGES


def load_seed_data(driver: DBDriver | None = None) -> int:
    """
    Load all seed edges into Neo4j.
    
    Args:
        driver: DBDriver instance (creates one from .env if not provided)
    
    Returns:
        Number of edges loaded
    """
    if driver is None:
        config = DBConfig()
        driver = DBDriver(config)
        driver.connect()
        should_close = True
    else:
        should_close = False

    edge_count = 0

    try:
        with driver.session() as session:
            for edge in SEED_EDGES:
                # Extract edge data
                gene_id = edge["gene"]["id"]
                disease_name = edge["disease"]["name"]
                pathogen = edge["disease"]["pathogen"]
                chromosome = edge["gene"]["chromosome"]
                allele = edge["gene"]["allele"]
                resistance_type = edge["gene"]["resistance_type"]
                confidence = edge["confidence"]
                source = edge["source"]
                treatment_action = edge["treatment"]["action"]
                iot_trigger = edge["treatment"]["iot_trigger"]
                
                # Build the comprehensive MERGE query
                # Handle null iot_trigger by using a unique treatment identifier
                treatment_id = f"{treatment_action}|{iot_trigger or 'no_trigger'}"
                
                query = """
                    MERGE (c:Crop {name: $crop_name})
                    
                    MERGE (v:Variety {name: $variety_name, crop: $crop_name})
                    MERGE (v)-[:BELONGS_TO]->(c)
                    
                    MERGE (g:Gene {id: $gene_id})
                    SET g.chromosome = $chromosome,
                        g.allele = $allele,
                        g.resistance_type = $resistance_type
                    
                    MERGE (v)-[:CARRIES {confidence: $confidence}]->(g)
                    
                    MERGE (d:Disease {name: $disease_name})
                    SET d.pathogen = $pathogen
                    
                    MERGE (g)-[r:CONFERS_RESISTANCE_TO {confidence: $confidence, source: $source}]->(d)
                    
                    MERGE (t:Treatment {action: $treatment_action})
                    SET t.iot_trigger = $iot_trigger
                    MERGE (d)-[:TREATED_BY]->(t)
                """
                
                for variety in edge.get("varieties", []):
                    session.run(
                        query,
                        crop_name=variety["crop"],
                        variety_name=variety["name"],
                        gene_id=gene_id,
                        chromosome=chromosome,
                        allele=allele,
                        resistance_type=resistance_type,
                        disease_name=disease_name,
                        pathogen=pathogen,
                        confidence=confidence,
                        source=source,
                        treatment_action=treatment_action,
                        iot_trigger=iot_trigger,
                    )
                
                edge_count += 1
                if edge_count % 5 == 0:
                    print(f"  Loaded {edge_count} / {len(SEED_EDGES)} edges...")
        
        print(f"✓ Loaded {edge_count} seed edges into Neo4j")
        return edge_count
    
    finally:
        if should_close:
            driver.close()
