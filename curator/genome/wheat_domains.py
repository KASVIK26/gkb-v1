"""Enrich wheat's ref_gene rows (NCBI RefSeq Gnomon gene models, no domain data of their own)
with real InterPro-domain-based NLR/RLK classification, by coordinate overlap against IWGSC's own
independently-called gene annotation (which does carry InterPro/Pfam/GO functional annotation).

Why coordinate overlap and not ID matching: NCBI (Gnomon "LOC..." IDs) and IWGSC ("TraesCS..." IDs)
ran two independent gene-calling pipelines over the *same* IWGSC RefSeq v2.1 assembly -- there is
no ID crosswalk between them (checked: iwgsc_refseq_all_correspondances.zip only cross-references
IWGSC's own annotation versions against each other, v1.0/v1.1/v2.1, never NCBI IDs). Verified
before writing any of this that the two coordinate systems are the same physical genome (NCBI's
LOC123183831 at 1,142,839-1,144,428 on 1A and IWGSC's TraesCS1A03G0004000 at 1,142,826-1,144,427
on Chr1A are the same gene, off by a few bp of independent UTR-boundary calling).

Downloaded 2026-09-26 from URGI (urgi.versailles.inrae.fr/download/iwgsc/IWGSC_RefSeq_Annotations/v2.1/):
    iwgsc_refseqv2.1_functional_annotation.zip  (InterPro/Pfam/GO per TraesCS gene)
    iwgsc_refseqv2.1_gene_annotation_200916.zip (TraesCS gene coordinates, HC + LC confidence tiers)
"""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from curator.genome.refgenes import _classify_domains

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_RAW = ROOT_DIR / "data" / "raw"
FUNCTIONAL_ANNOTATION_CSV = DATA_RAW / "iwgsc_functional_annotation" / "iwgsc_refseqv2.1_functional_annotation.csv"
IWGSC_HC_GFF3 = (
    DATA_RAW / "iwgsc_gene_annotation" / "iwgsc_refseqv2.1_gene_annotation_200916"
    / "iwgsc_refseqv2.1_annotation_200916_HC.gff3"
)


def load_iwgsc_interpro_domains(csv_path: Path = FUNCTIONAL_ANNOTATION_CSV) -> dict[str, set[str]]:
    """TraesCS gene ID -> set of its InterPro accessions ('IPR......', no 'InterPro:' prefix)."""
    domains: dict[str, set[str]] = {}
    with csv_path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["f.type"] != "InterPro":
                continue
            domains.setdefault(row["g2.identifier"], set()).add(row["f.name"])
    return domains


def load_iwgsc_gene_intervals(gff_path: Path = IWGSC_HC_GFF3) -> pd.DataFrame:
    """chromosome (e.g. '1A', 'Chr' prefix stripped), start_bp, end_bp, traescs_id -- one row per
    IWGSC HC gene feature, sorted by (chromosome, start_bp) for the overlap sweep below."""
    rows = []
    with gff_path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line or line[0] == "#":
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 9 or parts[2] != "gene":
                continue
            chromosome = parts[0].removeprefix("Chr")
            gene_id = next((kv[3:] for kv in parts[8].split(";") if kv.startswith("ID=")), None)
            if not gene_id:
                continue
            rows.append({"chromosome": chromosome, "start_bp": int(parts[3]), "end_bp": int(parts[4]), "traescs_id": gene_id})
    df = pd.DataFrame(rows)
    return df.sort_values(["chromosome", "start_bp"]).reset_index(drop=True)


def overlap_join(ncbi_genes: pd.DataFrame, iwgsc_genes: pd.DataFrame) -> dict[str, str]:
    """locus_id -> traescs_id for NCBI genes with exactly one overlapping IWGSC HC gene.

    Two-pointer sweep per chromosome (both inputs sorted by start_bp, and neither input's own
    intervals overlap each other -- they're each one caller's non-overlapping gene models) rather
    than an O(n*m) pairwise check. NCBI genes with zero or more-than-one overlapping IWGSC gene are
    left out entirely -- classifying from an ambiguous multi-gene overlap would be a guess, not a
    grounded transfer.
    """
    result: dict[str, str] = {}
    for chromosome, ncbi_chr in ncbi_genes.sort_values(["chromosome", "start_bp"]).groupby("chromosome"):
        iwgsc_chr = iwgsc_genes[iwgsc_genes["chromosome"] == chromosome]
        if iwgsc_chr.empty:
            continue
        iwgsc_records = iwgsc_chr.to_dict("records")
        j = 0
        for ncbi in ncbi_chr.to_dict("records"):
            while j < len(iwgsc_records) and iwgsc_records[j]["end_bp"] < ncbi["start_bp"]:
                j += 1
            hits = []
            k = j
            while k < len(iwgsc_records) and iwgsc_records[k]["start_bp"] <= ncbi["end_bp"]:
                if iwgsc_records[k]["end_bp"] >= ncbi["start_bp"]:
                    hits.append(iwgsc_records[k]["traescs_id"])
                k += 1
            if len(hits) == 1:
                result[ncbi["locus_id"]] = hits[0]
    return result


def classify_wheat_ref_genes(
    *, refgenes_parquet: Path, functional_annotation_csv: Path = FUNCTIONAL_ANNOTATION_CSV, iwgsc_gff: Path = IWGSC_HC_GFF3
) -> pd.DataFrame:
    """Return the wheat refgenes DataFrame with is_nlr/nlr_class/domains filled in wherever a
    confident 1:1 coordinate overlap with an IWGSC HC gene carrying InterPro domains was found."""
    ncbi_genes = pd.read_parquet(refgenes_parquet)
    iwgsc_genes = load_iwgsc_gene_intervals(iwgsc_gff)
    traescs_domains = load_iwgsc_interpro_domains(functional_annotation_csv)

    locus_to_traescs = overlap_join(ncbi_genes, iwgsc_genes)

    is_nlr_col, nlr_class_col, domains_col = [], [], []
    for row in ncbi_genes.itertuples(index=False):
        traescs_id = locus_to_traescs.get(row.locus_id)
        interpro_ids = traescs_domains.get(traescs_id, set()) if traescs_id else set()
        if interpro_ids:
            is_nlr, nlr_class = _classify_domains(interpro_ids)
            domains = list(row.domains) + [f"InterPro:{d}" for d in sorted(interpro_ids)]
        else:
            is_nlr, nlr_class, domains = False, None, list(row.domains)
        is_nlr_col.append(is_nlr)
        nlr_class_col.append(nlr_class)
        domains_col.append(domains)

    ncbi_genes = ncbi_genes.copy()
    ncbi_genes["is_nlr"] = is_nlr_col
    ncbi_genes["nlr_class"] = nlr_class_col
    ncbi_genes["domains"] = domains_col
    return ncbi_genes
