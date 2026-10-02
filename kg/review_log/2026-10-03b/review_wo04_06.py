"""Reviewer decisions for WO04, WO05, WO06 (2026-10-03; reviewer: Claude, for the project owner; a crop scientist reviews the live graph).
Input: batches/WO04.jsonl, WO05.jsonl, WO06.jsonl.  Output: batches/WO0N.reviewed.jsonl.  Every edit is either a quote rebuilt from the source's own
text (and re-checked by the verifier), an alias made of words that are literally in the quote, a corrected evidence type, or a drop."""

import json
import re

from curator.graph.quote_audit import fetch_source_text, normalise

DROP = {
    "WO06-0042": "GWAS marker-to-QTL links: header carries footnote letters; low value for a marker that is only the QTL's own tag",
    "WO06-0043": "as WO06-0042", "WO06-0044": "as WO06-0042", "WO06-0045": "as WO06-0042",
    "WO06-0053": "SNP ids contain commas (Gm18_57,223,391) and the model's sentence skips parts of the source without marking the cut",
    "WO06-0054": "as WO06-0053", "WO06-0055": "as WO06-0053", "WO06-0056": "as WO06-0053",
}


def load(n):
    return [json.loads(line) for line in open(f"batches/WO{n}.jsonl", encoding="utf-8")]


def save(n, rows):
    open(f"batches/WO{n}.reviewed.jsonl", "w", encoding="utf-8").write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


# ───────────────────────────── WO04 ─────────────────────────────
CAPTION = "Known genes for resistance to Powdery mildew, Fusarium head blight and Septoria tritici blotch from landraces, wild relatives and synthetic wheat."
HEADER = "Diseases | Source of Resistance | Genes"
SRC_RE = r"(?:Triticum|Aegilops|Thinopyrum|Leymus|Elymus)\s+[A-Za-z\.]+|Secale cereale|Haynaldia villosum"


def catalogue_rows():
    """(disease cell, source cell, genes cell) for every row of the review's resistance-gene table, from the paper's own text."""
    raw = fetch_source_text("pmid:27458472")
    block = raw[raw.index(HEADER) + len(HEADER): raw.index("Examples of resistance genes for diseases and pests from rye")]
    disease_cells = [(m.start(), m.group(0).strip()) for m in re.finditer(r"(?:Powdery mildew \(Blumeria graminis f\. sp\. tritici\)|Fusarium head blight \(Fusarium graminearum\)|Septoria tritici blotch \([^)]*\))", block)]
    rows = []
    for m in re.finditer(rf"(?P<src>{SRC_RE})\s*\|\s*(?P<genes>.+?)(?=\s+(?:{SRC_RE})\s*\||\s+Fusarium head blight|\s+Septoria|$)", block, flags=re.S):
        disease = [d for pos, d in disease_cells if pos < m.start()][-1]
        rows.append((disease, m.group("src").strip(), re.sub(r"\s+", " ", m.group("genes")).strip()))
    return rows


def gene_tokens(genes_cell):
    return {t.strip(" ,.").lower() for t in re.split(r"[,\s]+", genes_cell) if t and t.lower() != "and"}


WILT_HEADER = "Fusarium Race | Name of Resistance Gene | Number and Nature of Wilt Resistance Gene | Effect of Resistance Gene on Wilting | Symptoms"
_H1 = "1A | h1 (syn FOC-1) | Trigenic | Late wilting | Wilting | [57]"
WILT = {   # candidate -> (race, effect, the row exactly as the source prints it; h2 and H3 are the next two cells of the race-1A row)
    "WO04-0085": ("1A", "late wilting", "1A | h1 (syn FOC-1) | Trigenic | Late wilting | Wilting"),
    "WO04-0086": ("1A", "late wilting", _H1 + " h2 | Late wilting"),
    "WO04-0087": ("1A", "late wilting", _H1 + " h2 | Late wilting H3 | Late wilting"),
    "WO04-0088": ("2", "complete resistance", "2 | FOC-2 | Monogenic | Complete resistance | Wilting"),
    "WO04-0089": ("3", "complete resistance", "3 | FOC-3/FOC-3 | Monogenic | Complete resistance | Wilting"),
    "WO04-0090": ("4", "complete resistance", "4 | FOC-4 | Monogenic recessive | Complete resistance | Wilting"),
    "WO04-0091": ("5", "complete resistance", "5 | FOC-5/FOC-5 | Monogenic | Complete resistance | Wilting"),
}


def review_wo04():
    rows, table, out = load("04"), catalogue_rows(), []
    for c in rows:
        cid = c["candidate_id"]
        if "Known genes" in c["quote"] and c["source"].get("pmid") == "27458472":
            gene = c["subject"]["text"].lower()
            hits = [r for r in table if gene in gene_tokens(r[2]) and r[1] in c["quote"]]  # a gene can be listed under two sources (Pm36)
            assert len(hits) == 1, (cid, gene, len(hits))
            disease, src, genes = hits[0]
            assert disease.lower().startswith(c["object"]["text"].lower()[:8]), (cid, disease, c["object"])
            c["quote"] = f"{CAPTION} ... {HEADER} ... {disease} ... {src} | {genes}"
            props = dict(c["subject"].get("props") or {})
            if src.startswith(("Triticum spp", "Leymus")):          # not a usable species name (a genus placeholder / a misspelling in the source)
                props.pop("origin_species", None)
            else:
                props["origin_species"] = src
            c["subject"]["props"] = props or None
            if not props:
                c["subject"].pop("props")
        if cid in ("WO04-0060", "WO04-0064", "WO04-0068"):          # "...resistance to leaf, yellow and stem rust and powdery mildew"
            c["object"]["alias_in_quote"] = "leaf"
        if cid in ("WO04-0061", "WO04-0065", "WO04-0069"):
            c["object"]["alias_in_quote"] = "yellow"
        if cid == "WO04-0079":
            c["object"]["alias_in_quote"] = "pachyrhizi"            # the pathogen of soybean rust, named in the quote
        if cid == "WO04-0081":
            c["object"]["alias_in_quote"] = "SMV"
        if cid in WILT:   # chickpea Fusarium wilt genes, review Table (pmid:37109518); the source prints no "Table 1." in the caption
            race, effect, row = WILT[cid]
            c["quote"] = f"Genetics of resistance to races of the chickpea wilt Fusarium oxysporum f. sp. ciceris. ... {WILT_HEADER} ... {row}"
            c["qualifiers"]["spectrum"] = f"Fusarium oxysporum f. sp. ciceris race {race}; effect: {effect}"
            c["object"]["alias_in_quote"] = "chickpea wilt"      # the caption's own name for the disease
        if cid == "WO04-0082":
            c["quote"] = c["quote"].replace("(Glycine max [L.] Merr.)", "[Glycine max (L.) Merr.]")   # the paper's brackets, not the model's
        if cid == "WO04-0083":
            c["quote"] = c["quote"].replace("KEY MESSAGE:", "KEY MESSAGE")  # the source has no colon
            c["object"]["alias_in_quote"] = "pustule"
        out.append(c)
    save("04", out)
    return len(out)


# ───────────────────────────── WO05 ─────────────────────────────
def review_wo05():
    out = []
    for c in load("05"):
        cid = c["candidate_id"]
        if cid in ("WO05-0138", "WO05-0139", "WO05-0140", "WO05-0141", "WO05-0142"):
            # pmid:40678044 Table 3 "Inferred presence of the Lr gene(s)": postulated from seedling reactions against isogenic lines, not marker-typed
            c["qualifiers"]["method"] = "postulation"
            c["evidence_basis"] = "primary_postulation"
        if cid == "WO05-0139":
            c["object"]["alias_in_quote"] = "10+"      # the table's own shorthand ("Lr14a + 10+", "Lr23 + 10+")
        if cid == "WO05-0141":
            c["object"]["alias_in_quote"] = "1+"
        if "HD2189" in c["quote"]:                       # the source prints Lr, Sr, Yr in that row; the model had reordered the cells to match the header
            c["quote"] = c["quote"].replace("HD2189 | HD2963/HD1931 | Lr13+Lr34 | Yr2+Yr18 | Sr2+Sr11", "HD2189 | HD2963/HD1931 | Lr13+Lr34 | Sr2+Sr11 | Yr2+Yr18")
        out.append(c)
    save("05", out)
    return len(out)


# ───────────────────────────── WO06 ─────────────────────────────
MQTL_CAPTION = "Results of the meta-analysis of quantitative trait loci (QTLs) controlling fusarium resistance in chickpea."
MQTL_HEADER = ("LG | Meta QTL | AIC value | Linked to race(s) | Map position (cM) | No. of initial QTLs | Mean R 2 (%) | L-marker | L-marker position (cM) | "
               "R-marker | R-marker position (cM) | No. of studies | Mean CI of initial QTLs | No. of genes")
STRIPE_CAPTION = ("Identification of significant (LOD > 2.5) QTL for stripe rust resistance, their chromosomal location, flanking markers "
                  "and explained phenotypic variance (R 2)")


def mqtl_rows():
    raw = fetch_source_text("doi:10.1002/tpg2.70004")
    block = raw[raw.index("No. of genes") + len("No. of genes"): raw.index("The quantitative trait locus (QTL)")]
    block = re.sub(r"\s+", " ", block).strip()
    rows = {}
    for m in re.finditer(r"(?:CaLG\d\d \| )?(MQTL\d) \| (.+?)(?= (?:CaLG\d\d \| )?MQTL\d \||$)", block):
        rows[m.group(1)] = f"{m.group(1)} | {m.group(2)}".strip()
    return rows


def review_wo06():
    mq, out = mqtl_rows(), []
    for c in load("06"):
        cid = c["candidate_id"]
        if cid in DROP:
            continue
        if cid in ("WO06-0040", "WO06-0041"):
            name = c["subject"]["text"]
            # "Average" labels the first row of that block; the 2D row follows the 5B row without repeating it
            row = {"QYr.iiwbr-5B": "Average QYr.iiwbr-5B 1376633|F|0–1207571|F|08.026.434.120.2",
                   "QYr.iiwbr-2D": "Average ... QYr.iiwbr-2D Xgwm484–Xcfd73 2.634.720.18.9"}[name]
            c["quote"] = f"{STRIPE_CAPTION} ... {row}"
            c["qualifiers"]["population"] = "Cappelle–Desprez × PBW 343 (F9 RIL population)"
        if c["subject"]["text"].startswith("MQTL") and re.fullmatch(r"MQTL\d", c["subject"]["text"]):
            row = mq[c["subject"]["text"]]
            cells = [x.strip() for x in row.split("|")]
            # cells: MQTL, [AIC], races, position, n_initial, mean_R2, Lmarker, Lpos, Rmarker, Rpos, n_studies, CI, n_genes  (AIC is blank in merged rows)
            assert c["qualifiers"]["left_marker"] in cells and c["qualifiers"]["right_marker"] in cells, (cid, cells)
            assert str(float(c["qualifiers"]["pve_pct"])) in cells, (cid, cells, c["qualifiers"]["pve_pct"])
            c["quote"] = f"{MQTL_CAPTION} ... {MQTL_HEADER} ... {row}"
            c["object"]["alias_in_quote"] = "fusarium resistance"   # the caption: "controlling fusarium resistance in chickpea" (the only Fusarium disease in scope there is wilt)
        out.append(c)
    save("06", out)
    return len(out)


if __name__ == "__main__":
    print("WO04", review_wo04(), "| WO05", review_wo05(), "| WO06", review_wo06())
