"""Test the Neo4j queries that power the API.

Needs a live Neo4j instance, so these run only with `-m integration`.
Legacy: replaced by Postgres CQ tests in Phase 2 (see TECH_STACK.md).
"""

from __future__ import annotations

import pytest

from curator.db import DBConfig, DBDriver

pytestmark = pytest.mark.integration


def test_query_all_varieties_wheat():
    """Test querying all wheat varieties and their resistance genes."""
    config = DBConfig()
    config.validate()
    driver = DBDriver(config)
    driver.connect()

    try:
        with driver.session() as session:
            query = """
                MATCH (crop:Crop {name: "wheat"})
                MATCH (crop)<-[:BELONGS_TO]-(v:Variety)
                MATCH (v)-[carries:CARRIES]->(g:Gene)
                MATCH (g)-[resistance:CONFERS_RESISTANCE_TO]->(d:Disease)
                MATCH (d)-[:TREATED_BY]->(t:Treatment)
                RETURN {
                  gene: g.id,
                  chromosome: g.chromosome,
                  disease: d.name,
                  confidence: resistance.confidence
                } as edge
                LIMIT 5
            """
            result = session.run(query)
            edges = [record["edge"] for record in result]
            
            assert len(edges) > 0, "Expected at least one wheat edge"
            assert all("gene" in edge for edge in edges)
            assert all("disease" in edge for edge in edges)
            print(f"✓ Found {len(edges)} wheat resistance genes")
            for edge in edges[:3]:
                print(f"  - {edge['gene']} vs {edge['disease']} ({edge['confidence']})")
    
    finally:
        driver.close()


def test_query_specific_variety():
    """Test querying a specific variety."""
    config = DBConfig()
    config.validate()
    driver = DBDriver(config)
    driver.connect()

    try:
        with driver.session() as session:
            query = """
                MATCH (variety:Variety {name: "Chinese Spring", crop: "wheat"})
                MATCH (variety)-[carries:CARRIES]->(g:Gene)
                MATCH (g)-[resistance:CONFERS_RESISTANCE_TO]->(d:Disease)
                MATCH (d)-[:TREATED_BY]->(t:Treatment)
                RETURN {
                  gene: g.id,
                  disease: d.name,
                  treatment: t.action
                } as edge
                LIMIT 10
            """
            result = session.run(query)
            edges = [record["edge"] for record in result]
            
            assert len(edges) > 0, "Expected resistance genes for Chinese Spring"
            print(f"✓ Found {len(edges)} resistance genes for Chinese Spring wheat")
    
    finally:
        driver.close()


def test_query_soybean():
    """Test querying soybean resistance genes."""
    config = DBConfig()
    config.validate()
    driver = DBDriver(config)
    driver.connect()

    try:
        with driver.session() as session:
            query = """
                MATCH (crop:Crop {name: "soybean"})
                MATCH (crop)<-[:BELONGS_TO]-(v:Variety)
                MATCH (v)-[carries:CARRIES]->(g:Gene)
                RETURN COUNT(g) as gene_count
            """
            result = session.run(query)
            gene_count = result.single()["gene_count"]
            
            assert gene_count > 0, "Expected soybean resistance genes"
            print(f"✓ Found {gene_count} soybean resistance genes")
    
    finally:
        driver.close()


if __name__ == "__main__":
    import sys
    
    try:
        test_query_all_varieties_wheat()
        test_query_specific_variety()
        test_query_soybean()
        print("\n✓ All Neo4j query tests passed!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Query test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
