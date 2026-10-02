"""Assemble the reviewed WO04-WO06 batches into curated files. Sources and entities are defined once (the KB or an earlier batch may already
define them); display names keep the source's letters but get consistent spacing; vaguer duplicates of existing claims are dropped."""

import re
from pathlib import Path

import yaml

from curator.cli import _build_bundle

OUT = {
    "kg/curated/gene_resistance_catalogue_v1.yaml": ("kg/incoming/WO04r.yaml",
        "Gene -> disease resistance statements from review articles and gene papers (work order WO04: Pm/Fhb gene catalogue incl. donor species, rust genes,\n"
        "soybean Rpp/Rsv/Rcs, chickpea Fusarium wilt genes by race). Found by ChatGPT deep research, verified by `agrihub kg ingest-candidates`, reviewed\n"
        "claim-by-claim 2026-10-03 (kg/review_log/2026-10-03b_wo04-wo06.md). Evidence stays `llm:` (discounted)."),
    "kg/curated/variety_gene_postulations_v1.yaml": ("kg/incoming/WO05r.yaml",
        "Which gene(s) popular Indian wheat varieties carry, from the rust-resistance review table (pmid:33013989, stated) and the IARI Lr gene postulation\n"
        "(pmid:40678044). Work order WO05, reviewed 2026-10-03 (kg/review_log/2026-10-03b_wo04-wo06.md). Evidence stays `llm:` (discounted)."),
    "kg/curated/qtl_meta_analyses_v1.yaml": ("kg/incoming/WO06r.yaml",
        "QTL for disease resistance: 39 powdery-mildew meta-QTLs (pmid:39022610), 2 stripe-rust QTLs in Cappelle-Desprez x PBW 343, 7 chickpea Fusarium\n"
        "wilt meta-QTLs. Work order WO06, reviewed 2026-10-03 (kg/review_log/2026-10-03b_wo04-wo06.md). Evidence stays `llm:` (discounted)."),
}


def tidy_variety_name(name: str) -> str:
    name = re.sub("[‐-―−]", "-", name)
    if name.isupper() and not re.search(r"\d", name) and len(name) > 3:
        return name.capitalize()                                     # SONALIKA -> Sonalika
    return re.sub(r"^([A-Za-z]+)(\d)", r"\1 \2", name)               # HD2285 -> HD 2285, C306 -> C 306


bundle = _build_bundle()
taken_sources = {s.id for s in bundle.sources}
taken_entities = {e.id for e in bundle.entities}
specific = {(c.subject_id, c.object_id) for c in bundle.claims
            if c.type.value == "GENE_CONFERS_RESISTANCE" and c.qualifiers.get("resistance_type") != "unknown"}
dropped = []
for out, (path, header) in OUT.items():
    doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    sources, entities, claims = [], [], []
    for s in doc.get("sources") or []:
        if s["id"] not in taken_sources:
            taken_sources.add(s["id"]); sources.append(s)
    for e in doc.get("entities") or []:
        if e["id"] not in taken_entities:
            taken_entities.add(e["id"])
            if e["type"] == "Variety":
                e["name"] = tidy_variety_name(e["name"])
            entities.append(e)
    for c in doc.get("claims") or []:
        if c["type"] == "GENE_CONFERS_RESISTANCE" and c["qualifiers"].get("resistance_type") == "unknown" and (c["subject"], c["object"]) in specific:
            dropped.append((c["subject"], c["object"]))
            continue
        claims.append(c)
    used = {c["subject"] for c in claims} | {c["object"] for c in claims}
    entities = [e for e in entities if e["id"] in used]                     # nothing orphaned by a dropped claim
    body = yaml.safe_dump({"sources": sources, "entities": entities, "claims": claims}, sort_keys=False, allow_unicode=True, width=1000)
    Path(out).write_text("".join(f"# {line}\n" for line in header.splitlines()) + "\n" + body, encoding="utf-8", newline="\n")
    print(out, "| sources", len(sources), "| entities", len(entities), "| claims", len(claims))
print("dropped as vaguer duplicates of existing claims:", dropped)
