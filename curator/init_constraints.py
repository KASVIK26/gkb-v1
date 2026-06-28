"""Create the base uniqueness constraints for AgriHub KB."""

from __future__ import annotations

from curator.db import DBConfig, DBDriver


CONSTRAINT_STATEMENTS = (
    "CREATE CONSTRAINT gene_id_unique IF NOT EXISTS FOR (g:Gene) REQUIRE g.id IS UNIQUE",
    "CREATE CONSTRAINT variety_name_crop_unique IF NOT EXISTS FOR (v:Variety) REQUIRE (v.name, v.crop) IS UNIQUE",
    "CREATE CONSTRAINT disease_name_unique IF NOT EXISTS FOR (d:Disease) REQUIRE d.name IS UNIQUE",
)


def create_constraints(driver: DBDriver | None = None) -> None:
    """
    Create all base constraints in Neo4j.
    
    Args:
        driver: DBDriver instance (creates one from .env if not provided)
    """
    if driver is None:
        config = DBConfig()
        driver = DBDriver(config)
        driver.connect()
        should_close = True
    else:
        should_close = False

    try:
        with driver.session() as session:
            for statement in CONSTRAINT_STATEMENTS:
                session.run(statement)
                print(f"✓ {statement}")
    finally:
        if should_close:
            driver.close()
