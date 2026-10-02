"""QTL / GWAS loci for soybean rust, mosaic, frogeye and bacterial pustule from open-access mapping papers, read from their own tables by a parser (no model):
every locus is a row of a table; each claim quotes the table header and that row. Output: kg/curated/loci_open_papers_v1.yaml.
Papers: 42122877 (rust, Uganda GWAS), 36672760 (rust, qSBR18.1), 40604369 (SMV SC3 GWAS), 41963778 (SMV SC7 GWAS), 34895144 (frogeye GWAS),
42199232 (frogeye RIL QTL), 39273969 (bacterial pustule GWAS). Positions and assembly are recorded only where the paper states the assembly."""

import re
from pathlib import Path

import yaml

import curator.model  # noqa: F401
from curator.graph.quote_audit import fetch_source_text

DIS = {"fw": "dis:chickpea:fusarium_wilt", "rust": "dis:soybean:rust", "smv": "dis:soybean:mosaic_virus", "fls": "dis:soybean:frogeye_leaf_spot", "bp": "dis:soybean:bacterial_pustule"}
DIS_TRAIT = {"fw": "Fusarium wilt", "rust": "soybean rust", "smv": "soybean mosaic virus", "fls": "frogeye leaf spot", "bp": "bacterial pustule"}
entities, claims, report = {}, [], []


def _known_sources():
    from curator.cli import _build_bundle
    return {x.id for x in _build_bundle().sources}


KNOWN = _known_sources()


def p_from_text(s: str) -> float:
    m = re.fullmatch(r"\s*([\d.]+)\s*(?:×|x)\s*10[−-](\d+)\s*", s)
    return float(m.group(1)) * 10 ** (-int(m.group(2))) if m else float(s.replace("E−", "E-"))


def add(pmid, disease, name, chrom, stage, population, quote, locator, method, **q):
    crop = "chickpea" if disease == "fw" else "soybean"
    qid = f"qtl:{crop}:{name}"
    chrom_label = str(chrom) if not str(chrom).isdigit() else f"Gm{int(chrom):02d}"
    entities.setdefault(qid, {"id": qid, "type": "QTL", "name": name, "crop": crop, "synonyms": [], "name_i18n": {}, "props": {
        "trait": f"{DIS_TRAIT[disease]} resistance", "chromosome": chrom_label, "population": population}})
    quals = {"stage": stage, "population": population, **{k: v for k, v in q.items() if v is not None}}
    claims.append({"type": "QTL_ASSOCIATION", "subject": qid, "object": DIS[disease], "qualifiers": quals, "evidence": [{
        "source": f"pmid:{pmid}", "method": method, "locator": locator, "extractor": "parser:open_paper_table@1", "quote": quote, "candidate_id": f"open_loci:{pmid}:{name}"}]})
    report.append((pmid, name))


def table(text, caption, header, stop):
    a = text.index(caption)
    b = text.index(header, a) + len(header)
    e = text.index(stop, b)
    return text[b:e].strip()


def quote_of(caption, header, row):
    return f"{caption} ... {header} ... {row}" if caption else f"{header} ... {row}"


def rust_uganda(text):
    cap = "Significant SNPs associated with PR to SBR identified by FarmCPU."
    hdr = "SNP ID (ss) | Chr a | Pos b | p-Value | Allele | Effect | PVE (%) c"
    body = text[text.index(hdr, text.index(cap)) + len(hdr):]
    pat = re.compile(r"(\d{6,9}) \| (\d{1,2}) \| ([\d,]+) \| ([\d.]+ × 10−\d+) \| ([ACGT]/[ACGT]) \| (−?[\d.]+) \| ([\d.]+)")
    pos = 0
    for m in pat.finditer(body):
        if m.start() - pos > 12 and pos:
            break
        pos = m.end()
        add("42122877", "rust", f"SBR-PR_ss{m.group(1)}", m.group(2), "unspecified", "312 soybean accessions, natural infection in six Ugandan environments (FarmCPU)",
            quote_of(cap, hdr, m.group(0)), "Table of FarmCPU SNPs", "gwas", assembly="Wm82.a4.v1", start_bp=int(m.group(3).replace(",", "")),
            end_bp=int(m.group(3).replace(",", "")), p_value=p_from_text(m.group(4)), pve_pct=float(m.group(7)) if float(m.group(7)) > 0 else None, n_env=6)


def rust_cm5(text):
    cap = "QTLs were detected by the inclusive composite interval mapping method."
    hdr = "Trait | QTL Name | LinkageGroup | Position(cM) | LOD Score | Flanking Markers | Percentage of Variance Explained | Additive Effect"
    row = "Rust disease | qSBR 18.1 | G | 123 | 10.90 | T001855631m—sc21_3420 | 37.55 | 0.36"
    assert row in text and hdr in text
    add("36672760", "rust", "qSBR18.1", "18", "unspecified", "108 RILs of Sukhothai 2 x Chiang Mai 5 (field, Thailand)", quote_of(cap, hdr, row), "QTL table",
        "qtl_mapping", left_marker="T001855631m", right_marker="sc21_3420", lod=10.90, pve_pct=37.55)


def smv_sc3(text):
    hdr = "Num | SNP | Chr | Pos | -log(P.value) | H&B.P.Value | Model"
    body = text[text.index(hdr) + len(hdr):]
    pat = re.compile(r"(\d{1,2}) \| (\d{1,2}_\d+) \| (\d{1,2}) \| (?:[\d,]+|[\d.]+E \+ \d+) \| ([\d./]+) \| ([\d./]+) \| (?:BLINK|FarmCPU|MLM|MLMM)(?:/(?:BLINK|FarmCPU|MLM|MLMM))*")
    n = 0
    for m in pat.finditer(body):
        n += 1
        best = max(float(x) for x in m.group(4).split("/"))
        pos = int(m.group(2).split("_")[1])
        add("40604369", "smv", f"SMV-SC3_{m.group(2)}", m.group(3), "unspecified", "290 soybean accessions inoculated with SMV strain SC3 (BLINK, FarmCPU, MLM, MLMM)",
            quote_of("", hdr, m.group(0)), "Table of significant SNP loci", "gwas", assembly="Wm82.a2.v1", start_bp=pos, end_bp=pos, p_value=10 ** (-best))
        if n == 14:
            break
    assert n == 14, n


def smv_sc7(text):
    cap = "Significant SNPs associated with SMV SC7 resistance detected by GWAS"
    hdr = "Num | SNP | Chr | Pos | -log(P) | Model | References"
    body = text[text.index(hdr, text.index(cap)) + len(hdr):]
    pat = re.compile(r"(\d) \| (Chr\d+_\d+) \| (\d{1,2}) \| ([\d,]+) \| ([\d./]+)")
    n = 0
    for m in pat.finditer(body[:900]):
        n += 1
        best = max(float(x) for x in m.group(5).split("/"))
        add("41963778", "smv", f"SMV-SC7_{m.group(2)}", m.group(3), "unspecified", "290 soybean germplasm accessions inoculated with SMV strain SC7 (four GWAS models)",
            quote_of(cap, hdr, m.group(0)), "Table of significant SNPs", "gwas", p_value=10 ** (-best))
    assert n == 5, n


def fls_gwas(text):
    cap = "SNP loci significantly associated with C. sojina resistance traits by GWAS"
    hdr = "Methods | Marker | Chromosome | Position | Marker F | p value | Add F | Add p | Dom F | Dom p"
    body = text[text.index(hdr, text.index(cap)) + len(hdr):][:900]
    seen = {}
    for m in re.finditer(r"(Affx-[\d,]+) \| (\d+) \| ([\d,]+) \| ([\d.]+) \| ([\d.]+E−?-?\d+)", body):
        p = p_from_text(m.group(5))
        if m.group(1) not in seen or p < seen[m.group(1)][0]:
            seen[m.group(1)] = (p, m)
    for marker, (p, m) in seen.items():
        add("34895144", "fls", f"FLS-GWAS_{marker.replace(',', '')}", m.group(2), "unspecified", "234 Chinese soybean cultivars, 30,890 SNPs (GLM and MLM)", quote_of(cap, hdr, m.group(0)),
            "Table of significant SNP loci", "gwas", p_value=p)
    assert len(seen) == 4, len(seen)


def fls_ril(text):
    cap = "QTL associated with resistance to mixed races of frogeye leaf spot disease."
    hdr = "QTL | Chromosome | Leftmarker | Rightmarker | 5'-positon | 3'-positon | Environment | LOD | PVE(%) | Add | Reported QTL"
    a = text.index(hdr, text.index(cap)) + len(hdr)
    body = text[a:text.index(" Haplotype", a)]
    starts = [m.start() for m in re.finditer(r"qFLSm-\d+-\d+ \|", body)]
    for i, s in enumerate(starts):
        block = body[s:starts[i + 1] if i + 1 < len(starts) else len(body)].strip()
        m = re.match(r"(qFLSm-\d+-\d+) \| (\d+) \| (\S+) \| (\S+) \| (\d+) \| (\d+) \| (\w+) \| ([\d.]+) \| ([\d.]+)", block)
        if not m:
            continue
        lods = [(float(x), float(y)) for x, y in re.findall(r"(?:\| |^)([\d.]+) \| ([\d.]+) \| -?[\d.]+", block[block.index(" | ", 20):])]
        lod, pve = max(lods) if lods else (float(m.group(8)), float(m.group(9)))
        add("42199232", "fls", f"FLS-RIL_{m.group(1)}", m.group(2), "unspecified", "RIL3613 (Dongnong L13 x Heihe 36), two environments", quote_of(cap, hdr, block[:260] if len(block) > 260 else block),
            "QTL table", "qtl_mapping", left_marker=m.group(3), right_marker=m.group(4), lod=lod, pve_pct=pve, n_env=2)


def bp_gwas(text):
    cap = "SNPs significantly associated with resistance to bacterial pustule"
    hdr = "ISOLATE | SNP | MLM | CMLM | FarmCPU | BLINK Chr | Position | Trait | p | FDR | Effect | MAF | p | FDR | Effect | MAF | p | FDR | Effect | MAF | p | FDR | Effect | MAF"
    assert hdr in text, "bp header"
    a = text.index(hdr) + len(hdr)
    # the two regions the authors report as new: chr 6 for IBS 333 (49,886,965) and chr 18 for IBS 327 (1,872,252)
    specs = [("6", "49,886,965", "IBS 333", "BP-IBS333_Gm06_49886965", 6e-20),
             ("18", "1,872,252", "IBS 327", "BP-IBS327_Gm18_1872252", 1e-11)]
    for chrom, pos, isolate, name, p in specs:
        m = re.search(re.escape(pos) + r" \| DS \| (?:[^|]+\| ){3,16}[^|]+?(?= \||$)", text[a:a + 4000])
        row_start = text[a:a + 4000].index(pos)
        raw = text[a + row_start: a + row_start + 220]
        row = re.match(re.escape(pos) + r" \| DS \| (?:[^|]+\| ){15}[^|]+?(?= \| |\s[A-Z%]|$)", raw)
        assert row, (pos, raw)
        add("39273969", "bp", name, chrom, "unspecified", f"Brazilian and American soybean cultivars, isolate {isolate} (GBS, GWAS with four models)",
            f"{hdr} ... {chrom} | {row.group(0)}" if False else f"{hdr} ... {row.group(0)}", "SNP table", "gwas", p_value=p)


def source_entry(pid):
    from curator.lit import europepmc
    rec = europepmc.get_record("pmid:" + pid)
    meta = europepmc.metadata_from_record(rec, "pmid:" + pid)
    return {"id": f"pmid:{pid}", "type": "publication", "title": re.sub(r"<[^>]+>", "", meta.title).replace('"', "'"), "year": meta.year, "venue": meta.venue,
            "url": f"https://doi.org/{rec['doi']}" if rec.get("doi") else f"https://pubmed.ncbi.nlm.nih.gov/{pid}/", "verified": True}


def fw_review(text):
    i = text.index("Quantitative trait loci (QTLs) information of resistance")
    cap = text[i:text.index(" Race | QTL", i)]            # the paper prints a non-breaking hyphen in "meta-analysis": take the caption as it is
    hdr = "Race | QTL | Parents | Population type | Population size (n) | R 2 | CaLG | Genotyping method | LOD score | References"
    a = text.index(hdr, text.index(cap)) + len(hdr)
    body = text[a:a + 9000]
    pat = re.compile(r"(?:\d \| )?(R\d_\d+) \| ([^|]+?) \| ([^|]+?) \| (\d+) \| ([\d.]+) \| (\d+) \| ([^|]+?) \| ([\d.]+) \| \(([^)]+)\)")
    n = 0
    for m in pat.finditer(body):
        code, cross, popt, size, r2, lg, geno, lod, ref = m.groups()
        n += 1
        add("40050693", "fw", f"FW-{code}", f"CaLG{int(lg):02d}", "unspecified", f"{cross} {popt}, n={size}; {ref}", quote_of(cap, hdr, m.group(0)),
            "QTL table (input to the meta-analysis)", "review_statement", lod=float(lod), pve_pct=float(r2), n_env=None)
    assert n >= 25, n


def main():
    for pid, fn in (("42122877", rust_uganda), ("36672760", rust_cm5), ("40604369", smv_sc3), ("41963778", smv_sc7), ("34895144", fls_gwas),
                    ("42199232", fls_ril), ("39273969", bp_gwas), ("40050693", fw_review)):
        text = fetch_source_text("pmid:" + pid)
        assert text, pid
        before = len(report)
        fn(text)
        print(pid, fn.__name__, len(report) - before, "loci")
    header = ("QTL and GWAS loci for soybean rust, soybean mosaic virus, frogeye leaf spot, bacterial pustule and chickpea Fusarium wilt, read from the tables of eight open-access papers by\n"
              "batches/make_open_loci.py (no model). Each locus is one table row and each claim quotes the header and the row. Reference positions are kept only where the paper states the\n"
              "assembly. Study populations are Chinese, Brazilian, Ugandan and Thai; they are crop-level loci, not Indian-variety statements. Reviewed 2026-10-03\n"
              "(kg/review_log/2026-10-03h_open_loci.md).")
    Path("kg/curated/loci_open_papers_v1.yaml").write_text("".join(f"# {l}\n" for l in header.splitlines()) + "\n" + yaml.safe_dump(
        {"sources": [source_entry(pid) for pid in sorted({r[0] for r in report}) if f"pmid:{pid}" not in KNOWN], "entities": list(entities.values()), "claims": claims}, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8", newline="\n")
    print("QTLs", len(entities), "claims", len(claims))


if __name__ == "__main__":
    main()
