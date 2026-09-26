"""Build Europe PMC query strings from the disease vocabulary (RESEARCH_ROADMAP.md Sec 5.3).

Queries are generated programmatically from ``config/vocab/diseases.yaml`` -- never a hand-typed
PMID list (that pattern is exactly what produced the hallucinated-paper incident this project
already lived through; see archive/legacy_v1/literature_pipeline/README.md).
"""

from __future__ import annotations

from pathlib import Path

import yaml

VOCAB_DIR = Path(__file__).resolve().parents[2] / "config" / "vocab"

_CROP_TERMS = {
    "wheat": ['wheat', '"Triticum aestivum"'],
    "soybean": ['soybean', '"Glycine max"'],
    "chickpea": ['chickpea', '"Cicer arietinum"'],
}

_TOPIC_TERMS = ["resistance", "susceptib*", "environ*", "trigger", "management"]


def _quote_if_needed(term: str) -> str:
    return f'"{term}"' if " " in term and not term.startswith('"') else term


def build_disease_query(disease: dict) -> str:
    """Build one Europe PMC query string for a single disease entry from diseases.yaml.

    Mirrors the pattern given in RESEARCH_ROADMAP.md Sec 5.3, e.g. for dis:soybean:rust:
    (soybean OR "Glycine max") AND ("Soybean rust" OR "Asian soybean rust" OR "Phakopsora
    pachyrhizi") AND (resistance OR susceptib* OR environ* OR trigger OR management)
    """
    crop_terms = _CROP_TERMS[disease["crop"]]
    name_terms = [disease["name"], *disease.get("synonyms", [])]
    pathogen = disease.get("pathogen")
    if pathogen:
        name_terms.append(pathogen)
    name_clause = " OR ".join(_quote_if_needed(t) for t in name_terms)
    crop_clause = " OR ".join(crop_terms)
    topic_clause = " OR ".join(_TOPIC_TERMS)
    return f"({crop_clause}) AND ({name_clause}) AND ({topic_clause})"


def build_disease_queries(path: Path = VOCAB_DIR / "diseases.yaml") -> dict[str, str]:
    """Return {disease_id: query_string} for every disease in config/vocab/diseases.yaml."""
    vocab = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {disease["id"]: build_disease_query(disease) for disease in vocab["diseases"]}
