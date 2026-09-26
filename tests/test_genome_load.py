"""Tests for curator/genome/load.py against a throwaway PostgreSQL."""

from __future__ import annotations

from pathlib import Path

import psycopg
import pytest

from curator.genome.build import build_crop
from curator.genome.load import load_ref_genes
from curator.graph.pg import create_release_schema, set_search_path

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def parquet_dir(tmp_path: Path) -> Path:
    """A tiny, real refgenes_chickpea.parquet built from the mini fixture, not the full genome."""
    from curator.genome.refgenes import stream_ref_genes
    import pandas as pd

    records = [
        {
            "locus_id": g.locus_id, "crop": g.crop, "assembly": g.assembly, "chromosome": g.chromosome,
            "start_bp": g.start_bp, "end_bp": g.end_bp, "strand": g.strand, "description": g.description,
            "domains": list(g.domains), "is_nlr": g.is_nlr, "nlr_class": g.nlr_class,
        }
        for g in stream_ref_genes(FIXTURES / "mini_chickpea.gff3", crop="chickpea", assembly="ICC4958.gnm2")
    ]
    pd.DataFrame.from_records(records).to_parquet(tmp_path / "refgenes_chickpea.parquet", index=False)
    return tmp_path


def test_load_ref_genes_inserts_rows(pg_conn: psycopg.Connection, release_schema: str, parquet_dir: Path):
    create_release_schema(pg_conn, release_schema)
    counts = load_ref_genes(pg_conn, release_schema, parquet_dir=parquet_dir)
    assert counts == {"chickpea": 3}

    set_search_path(pg_conn, release_schema)
    (n,) = pg_conn.execute("SELECT count(*) FROM ref_gene").fetchone()
    assert n == 3

    (is_nlr, nlr_class, domains) = pg_conn.execute(
        "SELECT is_nlr, nlr_class, domains FROM ref_gene WHERE locus_id = %s",
        ("cicar.ICC4958.gnm2.ann1.Ca_01332",),
    ).fetchone()
    assert is_nlr is True
    assert nlr_class == "TNL"
    assert "InterPro:IPR002182" in domains


def test_load_ref_genes_is_idempotent(pg_conn: psycopg.Connection, release_schema: str, parquet_dir: Path):
    create_release_schema(pg_conn, release_schema)
    load_ref_genes(pg_conn, release_schema, parquet_dir=parquet_dir)
    load_ref_genes(pg_conn, release_schema, parquet_dir=parquet_dir)  # ON CONFLICT DO NOTHING

    set_search_path(pg_conn, release_schema)
    (n,) = pg_conn.execute("SELECT count(*) FROM ref_gene").fetchone()
    assert n == 3
