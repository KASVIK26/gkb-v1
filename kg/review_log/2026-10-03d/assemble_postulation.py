"""Assemble the two parser batches (AICRP Crop Protection 2021-22 and 2022-23 gene-postulation tables) into one curated file.

Both years go in one file so that a variety-gene pair postulated in both reports is ONE claim with two evidence rows (two documents).
Where the two reports disagree for an unflagged entry (neither year's genes for that class contains the other's), neither year is asserted.
"""

from collections import defaultdict
from pathlib import Path

import yaml

from curator.cli import _build_bundle

BATCHES = ["kg/incoming/aicrp_crop_protection_2021_22_postulation.yaml", "kg/incoming/aicrp_crop_protection_2022_23_postulation.yaml"]
OUT = "kg/curated/aicrp_gene_postulations_v1.yaml"
HEADER = ("Rust genes (Sr, Lr, Yr) that the AICRP Wheat & Barley Crop Protection reports 2021-22 and 2022-23 postulate for AVT entries that are released varieties in the KB\n"
          "(Tables 2.7-2.9 of each report; seedling tests with differential pathotypes at the IIWBR Regional Station, Flowerdale, and linkage inference). Read by\n"
          "parser:aicrp_postulation@1, no language model; entries marked * (different seed lot) are not used. Reviewed 2026-10-03\n"
          "(kg/review_log/2026-10-03d_aicrp_postulation.md). Method `postulation`, evidence `postulation_pedigree`.")

bundle = _build_bundle()
names = {e.id: e.name for e in bundle.entities}
taken_entities = {e.id for e in bundle.entities}

specs, entities = {}, []
by_class = defaultdict(lambda: defaultdict(set))          # (variety, class) -> year -> {gene ids}
for path in BATCHES:
    year = "21_22" if "2021_22" in path else "22_23"
    doc = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    for e in doc["entities"]:
        if e["id"] not in taken_entities and e["id"] not in {x["id"] for x in entities}:
            entities.append(e)
    for c in doc["claims"]:
        gene_class = c["object"].split(":")[-1][:2]
        by_class[(c["subject"], gene_class)][year].add(c["object"])
        key = (c["subject"], c["object"])
        if key in specs:
            specs[key]["evidence"].extend(c["evidence"])
        else:
            specs[key] = c

withheld = set()
for (variety, gene_class), years in by_class.items():
    if len(years) == 2:
        a, b = years.values()
        if not (a <= b or b <= a):
            withheld.add((variety, gene_class))
claims = [c for (v, g), c in specs.items() if (v, g.split(":")[-1][:2]) not in withheld]
used = {c["subject"] for c in claims} | {c["object"] for c in claims}
entities = [e for e in entities if e["id"] in used]
body = yaml.safe_dump({"sources": [], "entities": entities, "claims": claims}, sort_keys=False, allow_unicode=True, width=1000)
Path(OUT).write_text("".join(f"# {line}\n" for line in HEADER.splitlines()) + "\n" + body, encoding="utf-8", newline="\n")
two = sum(1 for c in claims if len({e["source"] for e in c["evidence"]}) == 2)
print(OUT, "| new genes", len(entities), "| claims", len(claims), f"({two} postulated in both reports)", "| evidence rows", sum(len(c['evidence']) for c in claims))
for v, g in sorted(withheld):
    print("withheld (the two reports disagree):", names.get(v, v), g, {y: sorted(s) for y, s in by_class[(v, g)].items()})
