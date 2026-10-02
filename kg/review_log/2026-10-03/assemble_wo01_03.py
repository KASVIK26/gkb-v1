"""Assemble the reviewed batches (parser output + WO02 + WO03) into final curated files. Run after the review scripts.

Removes what the KB (or an earlier batch) already defines -- sources and entities are defined once -- and tidies names that kept the
source's punctuation. Claims are never dropped here; a claim whose id already exists simply gains its extra evidence at load time.
"""

import re
from pathlib import Path

import yaml

from curator.cli import _build_bundle

NAME_FIX = {  # display names only; ids are unchanged (they ignore punctuation)
    "PK–472": "PK 472", "JS 75–46": "JS 75-46", "JS–76–205": "JS 76-205", "MACS–57": "MACS 57", "MACS-13": "MACS 13",
    "JS 90–41": "JS 90-41", "TAMS 98–21": "TAMS 98-21", "DDW47": "DDW 47", "DDW48": "DDW 48",
    "MACS-1188": "MACS 1188", "DSb-21": "DSb 21", "IPC2007-28": "IPC 2007-28",
}
OUT = {
    "kg/curated/aicrp_rust_reactions_v1.yaml": ["kg/incoming/aicrp_crop_protection_2021_22.yaml", "kg/incoming/aicrp_crop_protection_2022_23.yaml"],
    "kg/curated/aicrp_icar_reactions_v2.yaml": ["kg/incoming/WO02r.yaml"],
    "kg/curated/zones_and_pedigree_v1.yaml": ["kg/incoming/WO03r.yaml"],
}
HEADER = {
    "kg/curated/aicrp_rust_reactions_v1.yaml": "Adult-plant rust reactions of released wheat varieties from the AICRP Wheat & Barley Crop Protection reports 2021-22 and 2022-23,\n"
        "read by a parser (curator/graph/aicrp_rust.py, no language model). Reviewed 2026-10-03; decisions in kg/review_log/2026-10-03_wo01-wo03.md.",
    "kg/curated/aicrp_icar_reactions_v2.yaml": "Variety reactions from ICAR-IIPR / ICAR-IISR / AICRP reports, found by ChatGPT deep research (work order WO02), verified by\n"
        "`agrihub kg ingest-candidates` and reviewed claim-by-claim 2026-10-03 (kg/review_log/2026-10-03_wo01-wo03.md). Evidence stays `llm:` (discounted).",
    "kg/curated/zones_and_pedigree_v1.yaml": "Variety -> zone recommendations and parentage from ICAR pages and the IIWBR compendium, found by ChatGPT deep research (WO03),\n"
        "verified by `agrihub kg ingest-candidates` and reviewed claim-by-claim 2026-10-03 (kg/review_log/2026-10-03_wo01-wo03.md). Evidence stays `llm:`.",
}

bundle = _build_bundle()
taken_sources = {s.id for s in bundle.sources}
taken_entities = {e.id for e in bundle.entities}
summary = []
for out, ins in OUT.items():
    sources, entities, claims = [], [], []
    for path in ins:
        doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        for s in doc.get("sources") or []:
            if s["id"] not in taken_sources:
                taken_sources.add(s["id"])
                sources.append(s)
        for e in doc.get("entities") or []:
            if e["id"] not in taken_entities:
                taken_entities.add(e["id"])
                e["name"] = NAME_FIX.get(e["name"], re.sub("[‐-―−]", "-", e["name"]))
                entities.append(e)
        claims.extend(doc.get("claims") or [])
    body = yaml.safe_dump({"sources": sources, "entities": entities, "claims": claims}, sort_keys=False, allow_unicode=True, width=1000)
    Path(out).write_text("".join(f"# {line}\n" for line in HEADER[out].splitlines()) + "\n" + body, encoding="utf-8", newline="\n")
    summary.append((out, len(sources), len(entities), len(claims)))
for row in summary:
    print(row)
