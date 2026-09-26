"""Build manifest: checksums, git SHA, and counts recorded on every KG build (RESEARCH_ROADMAP.md
Phase 2 task 2.5). Written to kg/manifest.json, which is tracked in git -- so `git log -p
kg/manifest.json` is itself an audit trail of exactly which inputs, and which commit, produced
each release. No extra database table needed on top of promote.py's kg_meta.release_history.

Two kinds of file are tracked, and kept separate rather than lumped together:
  content_sources          -- files that literally supply entities/claims/evidence to the bundle
                               (config/vocab/diseases.yaml, notified_varieties.yaml, kg/curated/*)
  validation_dependencies  -- files that constrain what a build accepts without themselves
                               emitting entities (sensors.yaml's variable-name whitelist); a
                               change here can flip a build from passing to failing without
                               changing bundle content, so it belongs in the manifest too, but
                               it's not a "source" in the same sense.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from curator.graph.bundle import KGBundle
from curator.graph.variety_import import VARIETIES_PATH
from curator.graph.vocab_entities import VOCAB_DIR

ROOT_DIR = Path(__file__).resolve().parents[2]
KG_CURATED_DIR = ROOT_DIR / "kg" / "curated"
MANIFEST_PATH = ROOT_DIR / "kg" / "manifest.json"


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _relpath(path: Path) -> str:
    return str(path.relative_to(ROOT_DIR)).replace("\\", "/")


def _content_sources() -> dict[str, str]:
    files = [VOCAB_DIR / "diseases.yaml", VARIETIES_PATH, *sorted(KG_CURATED_DIR.glob("*.yaml"))]
    return {_relpath(p): _sha256(p) for p in files}


def _validation_dependencies() -> dict[str, str]:
    files = [VOCAB_DIR / "sensors.yaml"]
    return {_relpath(p): _sha256(p) for p in files}


def _git_state() -> tuple[str | None, bool]:
    """(HEAD commit SHA, tree has uncommitted changes), or (None, False) outside a git checkout."""
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT_DIR, capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"], cwd=ROOT_DIR, capture_output=True, text=True, check=True
            ).stdout.strip()
        )
        return sha, dirty
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None, False


def build_manifest(bundle: KGBundle, *, release: str | None = None) -> dict[str, Any]:
    git_sha, git_dirty = _git_state()
    return {
        "release": release,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "git_sha": git_sha,
        "git_dirty": git_dirty,
        "counts": {
            "sources": len(bundle.sources),
            "entities": len(bundle.entities),
            "claims": len(bundle.claims),
            "evidence": len(bundle.evidence),
        },
        "content_sources": _content_sources(),
        "validation_dependencies": _validation_dependencies(),
    }


def write_manifest(bundle: KGBundle, *, release: str | None = None, path: Path = MANIFEST_PATH) -> dict[str, Any]:
    manifest = build_manifest(bundle, release=release)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
