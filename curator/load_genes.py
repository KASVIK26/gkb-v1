"""Load parsed gene models into Neo4j."""

from __future__ import annotations

from curator.db import DBDriver


def _chunked(items: list[dict], chunk_size: int) -> list[list[dict]]:
    return [items[index : index + chunk_size] for index in range(0, len(items), chunk_size)]


def load_genes(driver: DBDriver, genes: list[dict], crop: str) -> int:
    """
    Load gene models into Neo4j with genome coordinates.

    Creates Gene nodes with:
    - id: Unique gene identifier
    - name: Gene name/symbol
    - chromosome: Mapped chromosome label (1A, Ca1, etc.)
    - start, end: Genomic coordinates (bp)
    - strand: +/-
    - length: Gene length (bp)
    - crop: Associated crop

    Args:
        driver: DBDriver instance (must be connected)
        genes: List of gene dicts from parse_gff3()
        crop: Crop name (wheat, soybean, chickpea)

    Returns:
        Number of genes loaded
    """
    count = 0
    
    # Create index on chromosome+crop for fast lookups
    index_query = """
    CREATE INDEX IF NOT EXISTS FOR (g:Gene) ON (g.crop, g.chromosome)
    """
    driver.run(index_query)

    # Load genes in batches with idempotent MERGE
    batch_size = 500
    query = """
    UNWIND $genes AS gene
    MERGE (g:Gene {id: gene.id})
    SET g.name = gene.name,
        g.chromosome = gene.chromosome,
        g.start = gene.start,
        g.end = gene.end,
        g.strand = gene.strand,
        g.length = gene.length,
        g.crop = $crop,
        g.updated_at = timestamp()
    RETURN count(g) AS loaded
    """

    for batch in _chunked(genes, batch_size):
        try:
            driver.run(query, genes=batch, crop=crop)
            count += len(batch)
        except Exception as e:
            print(f"    WARNING: Error loading batch ending with {batch[-1]['id']}: {e}")
    
    return count
