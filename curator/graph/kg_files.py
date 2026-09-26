"""Load hand-curated KG source files (kg/curated/*.yaml) into a KGBundle.

File format — one YAML document per topic/dataset:

    sources:  [ {id, type, title, year?, venue?, url?, license?, verified}, ... ]
    entities: [ {id, type, name, crop?, synonyms?, props}, ... ]
    claims:   [ {type, subject, object, qualifiers?, status?, evidence: [...]}, ... ]

`subject`/`object` (not `subject_id`/`object_id`) for readability in the file; each claim's
`evidence` list nests directly under it since a claim without evidence can never be a
standalone thing in this model — see curator/model/claims.py. `source` in an evidence entry
is that source's id. See kg/curated/README.md for a full worked example.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from curator.graph.bundle import KGBundle
from curator.model import Claim, Entity, Evidence, Source


def _load_claim(spec: dict[str, Any]) -> tuple[Claim, list[Evidence]]:
    spec = dict(spec)
    evidence_specs = spec.pop("evidence", [])
    if not evidence_specs:
        raise ValueError(f"claim {spec.get('type')} {spec.get('subject')}->{spec.get('object')} has no evidence")

    claim = Claim(
        type=spec["type"],
        subject_id=spec["subject"],
        object_id=spec["object"],
        qualifiers=spec.get("qualifiers") or {},
        status=spec.get("status", "unreviewed"),
    )
    evidence = [
        Evidence(
            claim_id=claim.id,
            source_id=ev["source"],
            method=ev["method"],
            extractor=ev.get("extractor", "manual:curator"),
            locator=ev.get("locator"),
            quote=ev.get("quote"),
            reviewer=ev.get("reviewer"),
            reviewed_at=ev.get("reviewed_at"),
        )
        for ev in evidence_specs
    ]
    return claim, evidence


def load_curated_file(path: Path) -> KGBundle:
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    sources = [Source.model_validate(s) for s in doc.get("sources", [])]
    entities = [Entity.model_validate(e) for e in doc.get("entities", [])]

    claims: list[Claim] = []
    evidence: list[Evidence] = []
    for spec in doc.get("claims", []):
        claim, ev = _load_claim(spec)
        claims.append(claim)
        evidence.extend(ev)

    return KGBundle(entities=entities, sources=sources, claims=claims, evidence=evidence)


def load_curated_dir(dir_path: Path) -> KGBundle:
    if not dir_path.is_dir():
        return KGBundle()
    bundles = [load_curated_file(p) for p in sorted(dir_path.glob("*.yaml"))]
    return KGBundle.merge(*bundles) if bundles else KGBundle()
