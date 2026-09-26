"""Release schema + competency-question tests against a throwaway PostgreSQL."""

from __future__ import annotations

import psycopg
import pytest
from kg_toy import (
    LEAF, LOC1, LR1, M1, M2, MILDEW, PT2, Q1, SRC, STRIPE, TRIG, V1, V2, V3, YR1, Z1, Z2, toy_bundle,
)

from curator.graph.pg import GateError, create_release_schema, load_bundle, run_cq


@pytest.fixture()
def toy_schema(pg_conn: psycopg.Connection, release_schema: str) -> str:
    create_release_schema(pg_conn, release_schema)
    load_bundle(pg_conn, release_schema, toy_bundle(), allow_test_sources=True)
    return release_schema


def test_load_counts(pg_conn, toy_schema):
    bundle = toy_bundle()
    counts = pg_conn.execute(
        f"SELECT (SELECT count(*) FROM {toy_schema}.entity), (SELECT count(*) FROM {toy_schema}.claim),"
        f" (SELECT count(*) FROM {toy_schema}.evidence)"
    ).fetchone()
    assert counts == (len(bundle.entities), len(bundle.claims), len(bundle.evidence))


def test_release_schema_is_immutable(pg_conn, toy_schema):
    with pytest.raises(psycopg.errors.DuplicateSchema):
        create_release_schema(pg_conn, toy_schema)


def test_load_refuses_test_sources_by_default(pg_conn, release_schema):
    create_release_schema(pg_conn, release_schema)
    with pytest.raises(GateError, match="test source"):
        load_bundle(pg_conn, release_schema, toy_bundle())


def test_views_hide_rejected_claims(pg_conn, toy_schema):
    rows = run_cq(pg_conn, toy_schema, "cq11_reaction_gaps", zone_id=Z2)
    assert [(r["variety_id"], r["disease_id"]) for r in rows] == [(V3, MILDEW)]


def test_cq01_susceptible_varieties(pg_conn, toy_schema):
    rows = run_cq(pg_conn, toy_schema, "cq01_susceptible_varieties_in_zone", zone_id=Z1, disease_id=STRIPE)
    assert [(r["variety_id"], r["reaction"]) for r in rows] == [(V1, "S"), (V2, "MS")]
    assert all(r["sources"] == [SRC] for r in rows)


def test_cq03_genes_and_prevalent_defeating_pathotypes(pg_conn, toy_schema):
    recent = run_cq(pg_conn, toy_schema, "cq03_variety_genes_effectiveness", variety_id=V1, since_year=2020)
    assert [(r["gene_id"], r["method"], r["defeated_by_prevalent_pathotypes"]) for r in recent] == [
        (YR1, "marker", [PT2])
    ]
    later = run_cq(pg_conn, toy_schema, "cq03_variety_genes_effectiveness", variety_id=V1, since_year=2024)
    assert later[0]["defeated_by_prevalent_pathotypes"] == []


def test_cq04_defeated_genes(pg_conn, toy_schema):
    rows = run_cq(pg_conn, toy_schema, "cq04_defeated_genes", crop="wheat")
    assert [(r["gene_id"], r["pathotype_id"], r["first_reported_year"]) for r in rows] == [(YR1, PT2, 2021)]
    assert run_cq(pg_conn, toy_schema, "cq04_defeated_genes", crop="soybean") == []
    assert len(run_cq(pg_conn, toy_schema, "cq04_defeated_genes", crop=None)) == 1


def test_cq05_qtl_nlr_candidates(pg_conn, toy_schema):
    (row,) = run_cq(pg_conn, toy_schema, "cq05_qtl_candidates", disease_id=STRIPE)
    assert row["qtl_id"] == Q1 and row["chromosome"] == "2B"
    assert row["genes_in_interval"] == 2 and row["nlr_candidates"] == [LOC1]


def test_cq06_markers_diagnostic_first(pg_conn, toy_schema):
    rows = run_cq(pg_conn, toy_schema, "cq06_markers_for_gene", gene_id=YR1)
    assert [(r["marker_id"], r["diagnostic"]) for r in rows] == [(M1, True), (M2, False)]


def test_cq07_triggers_with_citations(pg_conn, toy_schema):
    (row,) = run_cq(pg_conn, toy_schema, "cq07_disease_triggers", disease_id=STRIPE)
    assert row["trigger_id"] == TRIG and (row["bbch_from"], row["bbch_to"]) == (13, 75)
    assert {c["variable"] for c in row["conditions"]} == {"air_temp_c", "est_leaf_wet_h"}
    assert row["sources"] == [SRC] and row["quotes"]


def test_cq08_multi_disease_donors(pg_conn, toy_schema):
    rows = run_cq(pg_conn, toy_schema, "cq08_multi_disease_donors", crop="wheat", min_diseases=2)
    assert [(r["variety_id"], r["diseases"]) for r in rows] == [(V2, [LEAF, MILDEW])]


def test_cq09_zone_gene_reliance(pg_conn, toy_schema):
    rows = run_cq(pg_conn, toy_schema, "cq09_zone_gene_reliance", zone_id=Z1)
    assert [(r["gene_id"], r["n_varieties"], float(r["pct_of_zone_varieties"])) for r in rows] == [
        (YR1, 2, 100.0),
        (LR1, 1, 50.0),
    ]


def test_cq10_conflicts_ignore_race_specific_differences(pg_conn, toy_schema):
    rows = run_cq(pg_conn, toy_schema, "cq10_conflicting_reactions", crop="wheat")
    assert [(r["variety_id"], r["disease_id"], r["resistant_season"], r["susceptible_season"]) for r in rows] == [
        (V1, STRIPE, "2024", "2023")
    ]
    assert V3 not in {r["variety_id"] for r in rows}
