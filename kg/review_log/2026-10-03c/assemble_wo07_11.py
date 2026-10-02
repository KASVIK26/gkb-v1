"""Assemble the reviewed WO07-WO11 batches into curated files. Sources and entities are defined once (the KB or an earlier batch may already
define them); new pathotypes get the customary prefix (Pst / Pgt / Pt) so that '11' is not a bare number; vaguer duplicates of existing claims
are dropped."""

import re
from pathlib import Path

import yaml

from curator.cli import _build_bundle

OUT = {
    "kg/curated/pathotypes_iiwbr_v1.yaml": ("kg/incoming/WO07r.yaml",
        "Rust pathotypes reported by the IIWBR Mehtaensis newsletters (2020, 2026) and a genome-sequencing paper (pmid:36327308): which pathotypes of yellow, black\n"
        "and brown rust are predominant in India, the new brown-rust pathotype 52-6 and the genes it defeats. Work order WO07, reviewed 2026-10-03\n"
        "(kg/review_log/2026-10-03c_wo07-wo11.md). Evidence stays `llm:` (discounted)."),
    "kg/curated/advisories_official_v1.yaml": ("kg/incoming/WO08r.yaml",
        "Fungicide recommendations from two official documents: the PPQS AESA IPM package for wheat (2014) and the CIBRC Major Uses of Pesticides (Fungicides)\n"
        "as on 31.03.2024 (dose columns decoded with the table header, which is quoted). Work order WO08, reviewed 2026-10-03\n"
        "(kg/review_log/2026-10-03c_wo07-wo11.md). Evidence stays `llm:` (discounted)."),
    "kg/curated/fungicide_trials_v1.yaml": ("kg/incoming/WO09r.yaml",
        "Fungicide field trials: soybean anthracnose (Legume Research), wheat stem rust at Indore (AICRP crop protection report 2022-23), wheat leaf rust\n"
        "(Maharashtra). Work order WO09, reviewed 2026-10-03 (kg/review_log/2026-10-03c_wo07-wo11.md). Evidence stays `llm:` (discounted)."),
    "kg/curated/soybean_chickpea_reactions_and_pathogens_v1.yaml": ("kg/incoming/WO11r.yaml",
        "Soybean/chickpea: charcoal rot, dry root rot and anthracnose reactions of named varieties, causal organisms, SMV and frogeye resistance genes, chickpea\n"
        "rust fungicides. Work order WO11 (ChatGPT complete run + Grok run), reviewed 2026-10-03 (kg/review_log/2026-10-03c_wo07-wo11.md).\n"
        "Evidence stays `llm:` (discounted)."),
}
PATHOGEN_PREFIX = {"puccinia_striiformis_f_sp_tritici": "Pst", "puccinia_graminis_f_sp_tritici": "Pgt", "puccinia_triticina": "Pt"}


def tidy_variety_name(name: str) -> str:
    name = re.sub("[‐-―−]", "-", name)
    if name.isupper() and not re.search(r"\d", name) and len(name) > 3:
        return name.capitalize()
    return re.sub(r"^([A-Za-z]+)(\d)", r"\1 \2", name)


bundle = _build_bundle()
taken_sources = {s.id for s in bundle.sources}
taken_entities = {e.id for e in bundle.entities}
specific = {(c.subject_id, c.object_id) for c in bundle.claims
            if c.type.value == "GENE_CONFERS_RESISTANCE" and c.qualifiers.get("resistance_type") != "unknown"}
dropped = []
for out, (path, header) in OUT.items():
    doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    sources, entities, claims = [], [], []
    renames = {}
    for s in doc.get("sources") or []:
        if s["id"] not in taken_sources:
            taken_sources.add(s["id"]); sources.append(s)
    for e in doc.get("entities") or []:
        if e["id"] in taken_entities:
            continue
        taken_entities.add(e["id"])
        if e["type"] == "Variety":
            e["name"] = tidy_variety_name(e["name"])
        if e["type"] == "Advisory" and path.endswith("WO08r.yaml"):          # one name per practice: the dose tells the AESA and CIBRC entries apart
            props = e["props"]
            e["name"] = f"{props['active_ingredient'][0].upper()}{props['active_ingredient'][1:]} @ {props['dose']}"[:140]
        if e["type"] == "Pathotype":
            pathogen = e["id"].split(":")[1]
            prefix = PATHOGEN_PREFIX.get(pathogen)
            if prefix and not e["name"].startswith(prefix):
                e["synonyms"] = sorted({*(e.get("synonyms") or []), e["name"], f"{prefix}{e['name']}"})
                e["name"] = f"{prefix} {e['name']}"
        entities.append(e)
    for c in doc.get("claims") or []:
        if c["type"] == "GENE_CONFERS_RESISTANCE" and c["qualifiers"].get("resistance_type") == "unknown" and (c["subject"], c["object"]) in specific:
            dropped.append((c["subject"], c["object"]))
            continue
        claims.append(c)
    used = {c["subject"] for c in claims} | {c["object"] for c in claims}
    entities = [e for e in entities if e["id"] in used]
    body = yaml.safe_dump({"sources": sources, "entities": entities, "claims": claims}, sort_keys=False, allow_unicode=True, width=1000)
    Path(out).write_text("".join(f"# {line}\n" for line in header.splitlines()) + "\n" + body, encoding="utf-8", newline="\n")
    print(out, "| sources", len(sources), "| entities", len(entities), "| claims", len(claims))
print("dropped as vaguer duplicates of existing claims:", dropped)
