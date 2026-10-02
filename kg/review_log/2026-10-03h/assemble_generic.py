"""Assemble an ingested batch into a curated file: python batches/assemble_generic.py <incoming.yaml> <out.yaml> "<header>".
Drops a GENE_CONFERS_RESISTANCE claim with resistance_type 'unknown' when the KB already has a typed claim for the same pair; repeats no source or entity the KB has."""
import sys
from pathlib import Path

import yaml

from curator.cli import _build_bundle

src, out, header = sys.argv[1], sys.argv[2], sys.argv[3]
bundle = _build_bundle()
specific = {(c.subject_id, c.object_id) for c in bundle.claims if c.type.value == "GENE_CONFERS_RESISTANCE" and c.qualifiers.get("resistance_type") != "unknown"}
taken_e, taken_s = {e.id for e in bundle.entities}, {s.id for s in bundle.sources}
doc = yaml.safe_load(Path(src).read_text(encoding="utf-8"))
claims = [c for c in doc["claims"] if not (c["type"] == "GENE_CONFERS_RESISTANCE" and c["qualifiers"].get("resistance_type") == "unknown" and (c["subject"], c["object"]) in specific)]
print("dropped vaguer duplicates:", len(doc["claims"]) - len(claims))
used = {c["subject"] for c in claims} | {c["object"] for c in claims}
entities = [e for e in doc.get("entities") or [] if e["id"] not in taken_e and e["id"] in used]
sources = [s for s in doc.get("sources") or [] if s["id"] not in taken_s]
Path(out).write_text("".join(f"# {l}\n" for l in header.splitlines()) + "\n" + yaml.safe_dump({"sources": sources, "entities": entities, "claims": claims}, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8", newline="\n")
print(out, "| sources", len(sources), "| entities", len(entities), "| claims", len(claims))
