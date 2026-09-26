"""Unit tests for curator/lit/query_builder.py."""

from __future__ import annotations

from curator.lit.query_builder import build_disease_queries, build_disease_query


def test_build_disease_query_includes_crop_name_synonyms_and_pathogen():
    disease = {
        "id": "dis:soybean:rust",
        "crop": "soybean",
        "name": "Soybean rust",
        "synonyms": ["Asian soybean rust"],
        "pathogen": "Phakopsora pachyrhizi",
    }
    query = build_disease_query(disease)

    assert "Glycine max" in query
    assert "Soybean rust" in query
    assert "Asian soybean rust" in query
    assert "Phakopsora pachyrhizi" in query
    assert "resistance" in query


def test_build_disease_query_handles_missing_synonyms_and_pathogen():
    disease = {"id": "dis:wheat:leaf_rust", "crop": "wheat", "name": "Leaf rust"}
    query = build_disease_query(disease)
    assert "Leaf rust" in query
    assert "Triticum aestivum" in query


def test_build_disease_queries_covers_every_real_disease():
    """Regression test against the real vocabulary -- one query per disease ID, no crashes."""
    queries = build_disease_queries()
    assert len(queries) >= 17  # the 17 in-scope diseases as of this session
    assert "dis:soybean:rust" in queries
    assert "Phakopsora pachyrhizi" in queries["dis:soybean:rust"]
    assert "dis:chickpea:rust" in queries
