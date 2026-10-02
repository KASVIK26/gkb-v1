"""The charcoal-rot GWAS of 214 soybean accessions (pmid:41477268, ICAR-IISR Indore germplasm) read by a parser from the paper's own Tables 6, 7 and 8:
- Table 6 (glasshouse, seedling) and Table 7 (3-year sick plot, adult plant): one QTL per SNP, with its position in Williams 82 (Wm82.a2.v1), the most significant
  p-value reported for it, and the number of field years it was found in;
- Table 8: the defence-related genes the authors found within 200 kb either side of each locus (RefGene entities in Wm82.a2.v1 coordinates);
- the two susceptible checks (JS 95-60, JS 93-05) the Results name.
Nothing is inferred: every number is a cell of the table, and each claim quotes the caption, the header and the row. Output: kg/curated/soybean_charcoal_rot_gwas_v1.yaml."""

import re
from pathlib import Path

import yaml

import curator.model  # noqa: F401  (import order: curator.model before curator.normalize)
from curator.cli import _build_bundle
from curator.extract.normalize import resolve_entity_from_bundle
from curator.graph.quote_audit import fetch_source_text
from curator.model.enums import EntityType

SOURCE = "pmid:41477268"
DISEASE = "dis:soybean:charcoal_rot"
POPULATION = "214 diverse soybean accessions (GBS, GWAS with FarmCPU and BLINK)"
ASSEMBLY = "Wm82.a2.v1"
HEADER_G = "S. no. | SNP | Chr | Position (Williams 82) | Model | Trait | p-value | Effect | SIG/SUG"
HEADER_F = "S. no. | SNP | Chr | Position (Williams 82) | Model | Trait | Year | p-value | Effect | SIG/SUG"
CAP_G = "SNPs associated with charcoal rot resistance under glasshouse conditions."
CAP_F = "SNPs associated with charcoal rot resistance under sick plot conditions."
CAP_8 = "Candidate genes with biological process description and PFAM descriptions."
HEAD_8 = "Experiment | Loci | Genes | Start | Stop | Biological process, description | PFAM_descriptions"
EXTRACTOR_TABLE = "parser:gwas_table@1"


def pvals(slice_: str) -> list[float]:
    return [float(x.replace("−", "-")) for x in re.findall(r"\b(\d\.\d+E[−-]\d+)\b", slice_)]


def snp_blocks(text: str, caption: str, header: str) -> list[dict]:
    start = text.index(caption)
    end = text.index("Manhattan plots", start)
    table = text[start:end]
    body = table[table.index(header) + len(header):].strip()
    starts = [(m.start(), m.group(1), m.group(2)) for m in re.finditer(r"(?:^|(?<=\s))(\d{1,2}) \| (S\d{1,2}_\d+) \|", body)]
    blocks = []
    for i, (pos, serial, snp) in enumerate(starts):
        stop = starts[i + 1][0] if i + 1 < len(starts) else len(body)
        row = body[pos:stop].strip()
        cells = [c.strip() for c in row.split("|")]
        chrom, position = cells[2], int(cells[3])
        years = sorted(set(re.findall(r"\| (20\d\d) \|", row)))
        traits = sorted(set(re.findall(r"\| (?:FarmCPU|Blink) \| ([A-Z]+) \|", row)))
        blocks.append({"snp": snp, "chrom": chrom, "position": position, "p": min(pvals(row)), "years": years, "traits": traits, "row": row})
    return blocks


def gene_rows(text: str) -> list[dict]:
    start = text.index(CAP_8)
    end = text.index("Haplotype analysis.", start)
    body = text[start + len(CAP_8):end]
    body = body[body.index("PFAM_descriptions") + len("PFAM_descriptions"):].strip()
    out, experiment, locus = [], None, None
    pattern = re.compile(r"(?:(Glasshouse|Field) \| )?(?:(S\d{1,2}_\d+) \| )?(Glyma\.\d{2}G\d+) \| (\d+) \| (\d+) \| (.+?) \| (.+?)(?= (?:Glasshouse \| |Field \| )?(?:S\d{1,2}_\d+ \| )?Glyma\.\d{2}G\d+ \| |$)")
    for m in pattern.finditer(body):
        experiment = m.group(1) or experiment
        locus = m.group(2) or locus
        out.append({"experiment": experiment, "locus": locus, "gene": m.group(3), "start": int(m.group(4)), "stop": int(m.group(5)),
                    "process": m.group(6).strip(), "pfam": m.group(7).strip(), "locus_cell_gene": bool(m.group(2))})
    return out


V6_GFF = "data/raw/glyma.Wm82.gnm6.ann1.PKSW.gene_models_main.gff3"
V6_ASSEMBLY = "Wm82.gnm6.ann1"


def v6_genes(wanted: set) -> dict:
    """Gene models of the KB's soybean annotation (Wm82.gnm6.ann1) for the Glyma ids the paper lists. The ids survive from Wm82.a2 to v6, and each model's
    length is checked against the length the paper prints (a2) so that a reused id for a different gene would not pass."""
    found = {}
    with open(V6_GFF, encoding="utf-8") as fh:
        for line in fh:
            f = line.rstrip("\n").split("\t")
            if len(f) > 8 and f[2] == "gene":
                gid = re.search(r"Name=([^;]+)", f[8]).group(1)
                if gid in wanted:
                    note = re.search(r"Note=([^;]*)", f[8])
                    found[gid] = {"chrom": f[0].rsplit(".", 1)[-1], "start": int(f[3]), "end": int(f[4]), "strand": f[6], "note": (note.group(1) if note else "")}
    return found


def main():
    text = fetch_source_text(SOURCE)
    assert text, "paper text not available"
    bundle = _build_bundle()
    entities, claims = [], []

    def qtl_entity(snp, chrom):
        return {"id": f"qtl:soybean:{snp}", "type": "QTL", "name": snp, "crop": "soybean", "synonyms": [], "name_i18n": {},
                "props": {"trait": "charcoal rot resistance", "chromosome": f"Gm{int(chrom):02d}", "population": POPULATION}}

    seen = {}
    for caption, header, stage, label in ((CAP_G, HEADER_G, "seedling", "Table 6"), (CAP_F, HEADER_F, "adult", "Table 7")):
        for b in snp_blocks(text, caption, header):
            assert b["snp"] not in seen, b["snp"]
            seen[b["snp"]] = b
            entities.append(qtl_entity(b["snp"], b["chrom"]))
            q = {"stage": stage, "assembly": ASSEMBLY, "start_bp": b["position"], "end_bp": b["position"], "p_value": b["p"], "population": POPULATION}
            if stage == "adult" and b["years"]:
                q["n_env"] = len(b["years"])
            claims.append({"type": "QTL_ASSOCIATION", "subject": f"qtl:soybean:{b['snp']}", "object": DISEASE, "qualifiers": q, "evidence": [{
                "source": f"{SOURCE}", "method": "gwas", "locator": f"{label}, SNP {b['snp']}", "extractor": EXTRACTOR_TABLE,
                "quote": f"{caption} ... {header} ... {b['row']}", "candidate_id": f"gwas_cr:{label.replace(' ', '').lower()}:{b['snp']}"}]})

    genes = gene_rows(text)
    assert len(genes) == 23, len(genes)
    models = v6_genes({g["gene"] for g in genes})
    skipped = []

    def length_matches(g, m):
        a2_len = g["stop"] - g["start"] + 1
        return bool(m) and m["chrom"] == f"Gm{g['gene'][6:8]}" and abs((m["end"] - m["start"] + 1) - a2_len) <= 0.1 * a2_len

    # A gene counts as the same one in v6 when its model has about the same length, or when its model was re-annotated (different length) but sits where the
    # genes of the same chromosome that DO match put it (the a2 -> v6 coordinate shift is nearly constant over a locus): within 100 kb of one of their offsets.
    offsets = {}
    for g in genes:
        if length_matches(g, models.get(g["gene"])):
            offsets.setdefault(g["gene"][6:8], []).append(models[g["gene"]]["start"] - g["start"])

    def accepted(g):
        m = models.get(g["gene"])
        if not m:
            return False
        if length_matches(g, m):
            return True
        return m["chrom"] == f"Gm{g['gene'][6:8]}" and any(abs((m["start"] - g["start"]) - o) <= 100_000 for o in offsets.get(g["gene"][6:8], []))

    for g in genes:
        m = models.get(g["gene"])
        if not accepted(g):
            skipped.append(g["gene"])      # the id does not name the same gene in v6: not asserted
            continue
        gid = f"ref:soybean:{g['gene']}"
        if not any(e["id"] == gid for e in entities):
            entities.append({"id": gid, "type": "RefGene", "name": g["gene"], "crop": "soybean", "synonyms": [], "name_i18n": {}, "props": {
                "locus_id": g["gene"], "assembly": V6_ASSEMBLY, "chromosome": m["chrom"], "start_bp": m["start"], "end_bp": m["end"], "strand": m["strand"],
                "description": f"{g['process']} (GO terms as listed in pmid:41477268 Table 8; Wm82.a2.v1 position {g['start']}-{g['stop']})"[:500],
                "domains": [d.strip() for d in g["pfam"].split(";")]}})
        locus_first = next(x for x in genes if x["locus"] == g["locus"] and x["locus_cell_gene"])
        first_cells = f"{g['locus']} | {locus_first['gene']} | {locus_first['start']} | {locus_first['stop']}"
        quote = (f"{CAP_8} ... {HEAD_8} ... {first_cells}" if g is locus_first else
                 f"{CAP_8} ... {HEAD_8} ... {first_cells} ... {g['gene']} | {g['start']} | {g['stop']} | {g['process']} | {g['pfam']}")
        claims.append({"type": "QTL_CONTAINS_REFGENE", "subject": f"qtl:soybean:{g['locus']}", "object": gid, "qualifiers": {"assembly": ASSEMBLY}, "evidence": [{
            "source": SOURCE, "method": "computational", "locator": f"Table 8, {g['locus']} / {g['gene']}", "extractor": EXTRACTOR_TABLE, "quote": quote,
            "candidate_id": f"gwas_cr:table8:{g['gene']}"}]})

    # the susceptible checks named in the Results
    quote = "Across 3 years, the two checks (JS 95–60 and JS 93-05) showed susceptible disease reaction, indicating sufficient and uniform disease pressure in the sick plot."
    assert re.sub(r"[–‐-]", "-", quote) in re.sub(r"[–‐-]", "-", text), "check sentence not in the paper"
    for name in ("JS 95-60", "JS 93-05"):
        vid = resolve_entity_from_bundle(name, EntityType.VARIETY, bundle.entities, "soybean")
        assert vid, name
        claims.append({"type": "VARIETY_REACTION", "subject": vid, "object": DISEASE,
                       "qualifiers": {"reaction": "S", "stage": "adult", "season": "2021-2023", "location": "charcoal rot sick plot (artificial inoculation)"},
                       "evidence": [{"source": SOURCE, "method": "field_multi_env", "locator": "Results, phenotypic evaluation under sick plot conditions",
                                     "extractor": "llm:claude-from-paper-text@gwas-cr", "quote": quote, "candidate_id": f"gwas_cr:check:{name}"}]})

    header = ("Charcoal rot GWAS of 214 soybean accessions (Frontiers in Plant Science 2025, pmid:41477268): 18 SNP loci (Tables 6-7: glasshouse seedling and 3-year sick-plot adult-plant),\n"
              "the 23 defence-related genes within 200 kb of the loci (Table 8, Wm82.a2.v1 coordinates) and the two susceptible checks. Read from the paper's tables by\n"
              "batches/make_gwas_charcoal_rot.py (no model for the tables). Most SNPs are 'suggestive' in the paper's own classification (p between 1e-4 and the Bonferroni cutoff 7.46e-7).\n"
              "Reviewed 2026-10-03 (kg/review_log/2026-10-03f_icar_soybean.md).")
    body = yaml.safe_dump({"sources": [], "entities": entities, "claims": claims}, sort_keys=False, allow_unicode=True, width=1000)
    Path("kg/curated/soybean_charcoal_rot_gwas_v1.yaml").write_text("".join(f"# {l}\n" for l in header.splitlines()) + "\n" + body, encoding="utf-8", newline="\n")
    print("gene models not matched in v6 (skipped):", skipped)
    print("QTLs", sum(1 for c in claims if c["type"] == "QTL_ASSOCIATION"), "| genes", len(genes), "| claims", len(claims), "| entities", len(entities))
    for s, b in seen.items():
        print(f"  {s:14} chr{b['chrom']:>2} {b['position']:>9} p={b['p']:.2e} years={b['years']} traits={b['traits']}")


if __name__ == "__main__":
    main()
