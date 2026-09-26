"""Load refgenes_<crop>.parquet files into a release schema's `ref_gene` table (already created by
db/release_schema.sql). Kept separate from curator/graph/pg.py's load_bundle() -- ref_gene is
reference-genome data, not part of the curated Claim/Evidence/Entity bundle, and doesn't change
between releases the way curated content does.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import psycopg
from psycopg.types.json import Jsonb

from curator.genome.build import DATA_INTERIM
from curator.graph.pg import _check_schema, set_search_path


def load_ref_genes(conn: psycopg.Connection, schema: str, *, parquet_dir: Path = DATA_INTERIM) -> dict[str, int]:
    _check_schema(schema)
    set_search_path(conn, schema)
    counts: dict[str, int] = {}

    with conn.cursor() as cur:
        for path in sorted(parquet_dir.glob("refgenes_*.parquet")):
            crop = path.stem.removeprefix("refgenes_")
            df = pd.read_parquet(path)
            rows = [
                (
                    r.locus_id, r.crop, r.assembly, r.chromosome, int(r.start_bp), int(r.end_bp), r.strand,
                    r.description, list(r.domains), bool(r.is_nlr), r.nlr_class,
                )
                for r in df.itertuples(index=False)
            ]
            cur.executemany(
                "INSERT INTO ref_gene (locus_id, crop, assembly, chromosome, start_bp, end_bp, strand,"
                " description, domains, is_nlr, nlr_class) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                " ON CONFLICT (locus_id) DO NOTHING",
                rows,
            )
            counts[crop] = len(rows)
    return counts
