"""Tests for the agrihub CLI (curator/cli.py)."""

from __future__ import annotations

import json

import psycopg
import pytest
from typer.testing import CliRunner

from curator.cli import app
from curator.graph.pg import create_release_schema, set_search_path

runner = CliRunner()


def test_kg_build_reports_counts_and_passes():
    result = runner.invoke(app, ["kg", "build"])
    assert result.exit_code == 0, result.output
    assert "Build OK" in result.output
    assert '"claims"' in result.output


def test_kg_load_against_a_live_database(pg_conn: psycopg.Connection, pg_dsn: str, release_schema: str, tmp_path):
    tag = release_schema.removeprefix("kg_")
    manifest_path = tmp_path / "manifest.json"
    result = runner.invoke(
        app, ["kg", "load", "--release", tag, "--database-url", pg_dsn, "--manifest-path", str(manifest_path)]
    )
    assert result.exit_code == 0, result.output
    assert "Loaded release" in result.output

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["release"] == tag
    assert manifest["counts"]["entities"] > 0
    assert "config/vocab/diseases.yaml" in manifest["content_sources"]

    set_search_path(pg_conn, release_schema)
    (gene_count,) = pg_conn.execute(f"SELECT count(*) FROM {release_schema}.v_gene_resistance").fetchone()
    # wheat: Sr33, Sr35, Lr34 x3, Sr2, Sr31, Lr26, Yr9, Sr50, Fhb1, Lr21 (12)
    # wheat: Yr6NLR1, Yr6NLR2, Pm6, Pm37 x2 diseases, Fhb7 (6)
    # soybean: Rpp1, Rpp2, Rpp3, Rsv1, Rsv3, Rsv4, Rxp, Rcs3 (8)
    # chickpea: Ca_14301 (1)
    assert gene_count == 27


def test_kg_load_refuses_to_overwrite_an_existing_release(pg_conn: psycopg.Connection, pg_dsn: str, release_schema: str):
    create_release_schema(pg_conn, release_schema)
    result = runner.invoke(app, ["kg", "load", "--release", release_schema.removeprefix("kg_"), "--database-url", pg_dsn])
    assert result.exit_code != 0
