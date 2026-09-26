"""Tests for curator/graph/manifest.py (RESEARCH_ROADMAP.md Phase 2 task 2.5)."""

from __future__ import annotations

import hashlib
import json
import subprocess

from curator.graph.manifest import ROOT_DIR, build_manifest, write_manifest
from curator.graph.vocab_entities import VOCAB_DIR, reference_bundle


def test_manifest_has_expected_shape():
    manifest = build_manifest(reference_bundle(), release="2099_01_1")
    assert manifest["release"] == "2099_01_1"
    assert manifest["counts"]["entities"] == len(reference_bundle().entities)
    assert "built_at" in manifest


def test_manifest_release_defaults_to_none_for_a_bare_build():
    manifest = build_manifest(reference_bundle())
    assert manifest["release"] is None


def test_content_source_checksum_matches_the_real_file():
    manifest = build_manifest(reference_bundle())
    path = VOCAB_DIR / "diseases.yaml"
    expected = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    assert manifest["content_sources"]["config/vocab/diseases.yaml"] == expected


def test_sensors_yaml_is_a_validation_dependency_not_a_content_source():
    manifest = build_manifest(reference_bundle())
    assert "config/vocab/sensors.yaml" not in manifest["content_sources"]
    assert "config/vocab/sensors.yaml" in manifest["validation_dependencies"]


def test_git_sha_matches_the_real_head_commit():
    manifest = build_manifest(reference_bundle())
    real_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert manifest["git_sha"] == real_sha


def test_write_manifest_writes_valid_json(tmp_path):
    path = tmp_path / "manifest.json"
    written = write_manifest(reference_bundle(), release="2099_01_1", path=path)
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk == written
