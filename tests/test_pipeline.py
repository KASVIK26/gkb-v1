"""Unit tests for curator/run_pipeline.py -- no live Neo4j connection required."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from curator.loader import build_load_query
from curator.run_pipeline import (
    ValidationError,
    load_dataset_registry,
    select_downloaded_datasets,
    update_dataset_status,
    process_dataset,
)


def test_build_load_query_uses_merge_only():
    """Seed loader query must never contain CREATE (idempotency requirement)."""
    query = build_load_query()
    assert "MERGE (g:Gene" in query
    assert "CREATE" not in query


def test_load_dataset_registry_returns_dict(tmp_path):
    p = tmp_path / "datasets.yaml"
    p.write_text("datasets:\n  - id: wheat\n    status: downloaded\n", encoding="utf-8")
    registry = load_dataset_registry(p)
    assert isinstance(registry, dict)
    assert "datasets" in registry


def test_load_dataset_registry_empty_file(tmp_path):
    p = tmp_path / "datasets.yaml"
    p.write_text("", encoding="utf-8")
    registry = load_dataset_registry(p)
    assert registry.get("datasets") == []


def test_load_dataset_registry_invalid_top_level(tmp_path):
    p = tmp_path / "datasets.yaml"
    p.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(ValidationError, match="mapping at the top level"):
        load_dataset_registry(p)


def test_select_downloaded_datasets_filters_correctly(tmp_path):
    p = tmp_path / "datasets.yaml"
    p.write_text(
        "datasets:\n"
        "  - id: wheat\n    status: downloaded\n"
        "  - id: soybean\n    status: not_downloaded\n"
        "  - id: chickpea\n    status: loaded\n",
        encoding="utf-8",
    )
    registry = load_dataset_registry(p)
    downloaded = select_downloaded_datasets(registry)
    assert len(downloaded) == 1
    assert downloaded[0]["id"] == "wheat"


def test_select_downloaded_datasets_empty_registry():
    assert select_downloaded_datasets({"datasets": []}) == []


def test_select_downloaded_datasets_all_loaded():
    assert select_downloaded_datasets({"datasets": [{"id": "x", "status": "loaded"}]}) == []


def _make_registry(tmp_path, datasets):
    p = tmp_path / "datasets.yaml"
    p.write_text(yaml.dump({"datasets": datasets}, default_flow_style=False), encoding="utf-8")
    return p


def test_update_dataset_status_changes_status(tmp_path):
    p = _make_registry(tmp_path, [
        {"id": "wheat", "status": "downloaded"},
        {"id": "soybean", "status": "downloaded"},
    ])
    update_dataset_status("wheat", "loaded", p)
    updated = load_dataset_registry(p)
    statuses = {d["id"]: d["status"] for d in updated["datasets"]}
    assert statuses["wheat"] == "loaded"
    assert statuses["soybean"] == "downloaded"  # untouched


def test_update_dataset_status_missing_id_raises(tmp_path):
    p = _make_registry(tmp_path, [{"id": "wheat", "status": "downloaded"}])
    with pytest.raises(KeyError, match="nonexistent"):
        update_dataset_status("nonexistent", "loaded", p)


def test_update_dataset_status_is_idempotent(tmp_path):
    p = _make_registry(tmp_path, [{"id": "wheat", "status": "downloaded"}])
    update_dataset_status("wheat", "loaded", p)
    update_dataset_status("wheat", "loaded", p)
    registry = load_dataset_registry(p)
    assert registry["datasets"][0]["status"] == "loaded"


def test_process_dataset_skips_fasta(tmp_path):
    fasta = tmp_path / "dummy.fasta"
    fasta.write_text(">seq1\nACGT\n", encoding="utf-8")
    dataset = {
        "id": "soy_fasta",
        "crop": "soybean",
        "type": "reference_assembly",
        "local_path": str(fasta),
    }
    result = process_dataset(dataset)
    assert result["error"] is not None
    assert "Skipped" in result["error"]
    assert result["genes_parsed"] == 0


def test_process_dataset_file_not_found():
    dataset = {
        "id": "missing",
        "crop": "wheat",
        "type": "gene_annotation",
        "local_path": "/nonexistent/path/gene.gff.gz",
    }
    result = process_dataset(dataset)
    assert result["error"] is not None
    assert result["genes_parsed"] == 0
