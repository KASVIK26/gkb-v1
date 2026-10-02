"""WO13a -> kg/curated/rust_gene_links_v1.yaml. A gene -> disease claim with resistance_type 'unknown' is dropped when the KB already has a typed claim for the
same pair (the typed one is the better statement); sources and entities already in the KB are not repeated."""
from pathlib import Path

import yaml

from curator.cli import _build_bundle

OUT = "kg/curated/rust_gene_links_v1.yaml"
HEADER = ("Which disease each rust gene that Indian wheat varieties carry in the KB confers resistance to (Sr, Lr and Yr genes listed in the AICRP Crop Protection reports\n"
          "2021-22 and 2022-23 as stem, leaf and yellow rust resistance genes). Without these the 'variety carries gene' claims led nowhere. Work order WO13a, reviewed\n"
          "2026-10-03 (kg/review_log/2026-10-03e_gene_links.md). Resistance type is left 'unknown' (the reports do not say all-stage or adult-plant). Evidence stays `llm:` (discounted).")
bundle = _build_bundle()
specific = {(c.subject_id, c.object_id) for c in bundle.claims if c.type.value == "GENE_CONFERS_RESISTANCE" and c.qualifiers.get("resistance_type") != "unknown"}
taken_e, taken_s = {e.id for e in bundle.entities}, {s.id for s in bundle.sources}
doc = yaml.safe_load(Path("kg/incoming/WO13a.yaml").read_text(encoding="utf-8"))
claims = [c for c in doc["claims"] if (c["subject"], c["object"]) not in specific]
print("dropped (typed claim already exists):", sorted(c["subject"].split(":")[-1] for c in doc["claims"] if (c["subject"], c["object"]) in specific))
used = {c["subject"] for c in claims} | {c["object"] for c in claims}
entities = [e for e in doc["entities"] if e["id"] not in taken_e and e["id"] in used]
sources = [s for s in doc["sources"] if s["id"] not in taken_s]
body = yaml.safe_dump({"sources": sources, "entities": entities, "claims": claims}, sort_keys=False, allow_unicode=True, width=1000)
Path(OUT).write_text("".join(f"# {l}\n" for l in HEADER.splitlines()) + "\n" + body, encoding="utf-8", newline="\n")
print(OUT, "| entities", len(entities), "| claims", len(claims))
