"""The IARI leaf-rust gene table (pmid:40678044, "Seedling resistance genes characterized in Indian wheat genotypes/cultivars to leaf rust. Inferred presence of the
Lr gene(s) in Indian wheat collection": 86 genotypes, two columns of S. no. | Genotype | Lr gene(s)) read by a parser: one VARIETY_CARRIES_GENE claim (method postulation) per
gene of a cell, for the genotypes that are varieties the KB already has. "S" (seedling susceptible, no gene inferred) makes no claim; the lone "R" in "Lr24 + R" is not a gene symbol.
Output: kg/curated/lr_postulation_iari_v1.yaml."""

import re
from pathlib import Path

import yaml

import curator.model  # noqa: F401
from curator.cli import _build_bundle
from curator.extract.normalize import resolve_entity_from_bundle
from curator.graph.quote_audit import fetch_source_text
from curator.model.enums import EntityType
from curator.normalize.synonyms import AmbiguousName

SOURCE = "pmid:40678044"
CAPTION = ("Seedling resistance genes characterized in Indian wheat genotypes/cultivars to leaf rust. Inferred presence of the Lr gene(s) in Indian wheat collection.")
HEADER = "S. no. | Genotype/Cultivar | Lr gene(s) | S. no. | Genotype/Cultivar | Lr gene(s)"


GENES = r"(?:S|Lr\d+[a-z]?(?: ?\+ ?(?:\d+[a-z]?|R)\+?)*\+?)"
ROW = re.compile(r"(?P<n>\d{1,2}) \| (?P<name>[^|]+?) \| (?P<genes>" + GENES + r")(?= \| \d{1,2} \| | \d{1,2} \| |$)")


def rows(text: str) -> list[dict]:
    start = text.index(CAPTION)
    body = text[start + len(CAPTION):]
    body = body[body.index(HEADER) + len(HEADER):]
    body = body[:body.index("Graphical representation")].strip()
    out = [{"sno": int(m.group("n")), "name": m.group("name").strip(), "genes": m.group("genes").strip()} for m in ROW.finditer(body)]
    assert sorted(r["sno"] for r in out) == list(range(1, 87)), sorted(r["sno"] for r in out)[:5]
    return out


def symbols(cell: str) -> list[str]:
    """'Lr13 + 10+' -> ['Lr13', 'Lr10']; 'Lr24 + R' -> ['Lr24']; 'S' -> []."""
    cell = cell.strip()
    if cell == "S":
        return []
    parts = [p.strip() for p in cell.replace("+", " + ").split("+") if p.strip()]
    genes = []
    for p in parts:
        m = re.fullmatch(r"(?:Lr)?(\d+[a-z]?)", p)
        if m:
            genes.append("Lr" + m.group(1))
    return genes


def main():
    text = fetch_source_text(SOURCE)
    table = rows(text)
    bundle = _build_bundle()
    claims, entities, unknown, matched = {}, [], [], {}
    known_genes = {e.id for e in bundle.entities}
    for r in table:
        syms = symbols(r["genes"])
        if not syms:
            continue
        name = re.sub(r"\s*\(.*?\)\s*", " ", r["name"]).strip()
        try:
            vid = resolve_entity_from_bundle(name, EntityType.VARIETY, bundle.entities, "wheat")
        except AmbiguousName:
            vid = None
        if not vid:
            unknown.append(r["name"])
            continue
        matched[r["name"]] = vid
        row_text = f"{r['sno']} | {r['name']} | {r['genes']}"
        assert row_text in text, row_text
        for sym in syms:
            gid = resolve_entity_from_bundle(sym, EntityType.GENE, bundle.entities, "wheat") or f"gene:wheat:{sym}"
            if gid not in known_genes and not any(e["id"] == gid for e in entities):
                entities.append({"id": gid, "type": "Gene", "name": sym, "crop": "wheat", "synonyms": [], "name_i18n": {}, "props": {"symbol": sym}})
            claims[(vid, gid)] = {"type": "VARIETY_CARRIES_GENE", "subject": vid, "object": gid, "qualifiers": {"method": "postulation"}, "evidence": [{
                "source": SOURCE, "method": "postulation_pedigree", "locator": f"Seedling resistance genes table, row {r['sno']}", "extractor": "parser:lr_table@1",
                "quote": f"{CAPTION} ... {HEADER} ... {row_text}", "candidate_id": f"lr_iari:{r['sno']}:{sym}"}]}
    header = ("Which Lr genes Indian wheat varieties carry, from the IARI seedling-test and marker table of 86 genotypes (pmid:40678044, 'Inferred presence of the Lr gene(s)'),\n"
              "read by batches/make_lr_iari.py (no model); only genotypes that are varieties already in the KB. Reviewed 2026-10-03 (kg/review_log/2026-10-03g_gene_variety_links.md).")
    Path("kg/curated/lr_postulation_iari_v1.yaml").write_text("".join(f"# {l}\n" for l in header.splitlines()) + "\n" + yaml.safe_dump(
        {"sources": [], "entities": entities, "claims": list(claims.values())}, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8", newline="\n")
    print("table rows", len(table), "| varieties matched", len(matched), "| claims", len(claims), "| new genes", [e["id"] for e in entities])
    print("matched:", matched)
    print("not in KB:", unknown)


if __name__ == "__main__":
    main()
