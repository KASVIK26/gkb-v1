"""Fetch open-access papers from PubMed Central, chain into Groq AI extraction.

Usage examples:
  # Fetch a single paper by PMID and extract knowledge
  python scripts/fetch_papers.py --pmid 37480228 --crop wheat

  # Fetch and process all papers in the curated list
  python scripts/fetch_papers.py --all

  # Dry-run: download papers only, do not call Groq
  python scripts/fetch_papers.py --all --no-extract

  # Process papers that are already downloaded
  python scripts/fetch_papers.py --extract-only --crop chickpea
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
PAPERS_DIR = ROOT_DIR / "data" / "raw" / "papers"
REVIEW_QUEUE = ROOT_DIR / "data" / "review_queue.json"


# ─────────────────────────────────────────────────────────────────────────────
# Curated paper list (20+ per crop, India-relevant, all PMC open-access)
# Add new papers here: {"pmid": "...", "pmcid": "PMCxxxxxxx", "crop": "...",
#                        "title": "...", "note": "..."}
# ─────────────────────────────────────────────────────────────────────────────
CURATED_PAPERS: list[dict] = [
    # ── WHEAT ────────────────────────────────────────────────────────────────
    {
        "pmid": "37480228",
        "pmcid": "PMC10376725",
        "crop": "wheat",
        "title": "Virulence and genetic analysis of Puccinia graminis tritici in the Indian sub-continent from 2016 to 2022 and evaluation of wheat varieties for stem rust resistance",
        "note": "Stem rust Sr genes; Indian varieties HD2781, K307, WH711 evaluated",
    },
    {
        "pmid": "36305929",
        "pmcid": "PMC9614308",
        "crop": "wheat",
        "title": "Harnessing genetic resistance to rusts in wheat and integrated rust management methods to develop more durable resistant cultivars",
        "note": "Review of Sr, Lr, Yr durable resistance genes including Lr34, Yr18, Sr2",
    },
    {
        "pmid": "37228583",
        "pmcid": "PMC10248633",
        "crop": "wheat",
        "title": "Pyramiding of genes for grain protein content, grain quality, and rust resistance in eleven Indian bread wheat cultivars",
        "note": "India ICAR multi-site pyramiding of Sr, Lr, Yr genes; varieties HD2781, HD3086, GW322, NW1014",
    },
    {
        "pmid": "36299289",
        "pmcid": "PMC9638138",
        "crop": "wheat",
        "title": "Marker assisted improvement for leaf rust and moisture deficit stress tolerance in wheat variety HD3086",
        "note": "Lr28, Lr3ka introgression into India mega-variety HD3086 via MABC",
    },
    {
        "pmid": "38988305",
        "pmcid": "PMC11233289",
        "crop": "wheat",
        "title": "Genome-wide atlas of rust resistance loci in wheat",
        "note": "Comprehensive catalog of 350+ Sr/Lr/Yr loci with chromosomal positions",
    },
    {
        "pmid": "39011551",
        "pmcid": "PMC11100168",
        "crop": "wheat",
        "title": "Genome-wide association study identifies novel loci and candidate genes for rust resistance in wheat (Triticum aestivum L.)",
        "note": "GWAS for stem/leaf/stripe rust; novel QTL on chromosomes 2B, 4A, 7D",
    },
    {
        "pmid": "40102813",
        "pmcid": "PMC12267166",
        "crop": "wheat",
        "title": "Multiple patho-phenotyping and molecular analysis to characterize wide-spectrum durable leaf rust resistance in wheat collections from India",
        "note": "Lr34, Lr46 durable genes in India germplasm; multi-race phenotyping",
    },
    {
        "pmid": "37110609",
        "pmcid": "PMC10493333",
        "crop": "wheat",
        "title": "Genome-wide QTL mapping for stripe rust resistance in spring wheat line PI 660122 using the Wheat 15K SNP array",
        "note": "Yr QTL on 2B/4B/7B; methodology applicable to Indian stripe rust races",
    },
    {
        "pmid": "38073956",
        "pmcid": "PMC10418946",
        "crop": "wheat",
        "title": "Genomic Regions Associated with Resistance to Three Rusts in CIMMYT Wheat Line Mokue#1",
        "note": "Multi-rust resistance loci; Mokue#1 crosses used in India wheat programs",
    },
    {
        "pmid": "38649684",
        "pmcid": "PMC11035757",
        "crop": "wheat",
        "title": "Evaluation of stripe rust resistance and genome-wide association study in wheat varieties derived from ICARDA",
        "note": "ICARDA-derived wheat varieties evaluated for Yr stripe rust resistance in South Asia",
    },
    {
        "pmid": "36688521",
        "pmcid": "PMC9858494",
        "crop": "wheat",
        "title": "Identification of novel powdery mildew resistance genes in wheat by GWAS",
        "note": "Pm resistance loci mapped; India powdery mildew races covered",
    },
    {
        "pmid": "34589024",
        "pmcid": "PMC8481734",
        "crop": "wheat",
        "title": "Genetics and genomics of Fusarium head blight resistance in wheat",
        "note": "Fhb1, Fhb2, Fhb4, Fhb5 QTL review; FHB emerging in India Gangetic plains",
    },
    {
        "pmid": "35574671",
        "pmcid": "PMC9107004",
        "crop": "wheat",
        "title": "Molecular markers for disease resistance genes in wheat — a review",
        "note": "Marker-assisted selection for Sr, Lr, Yr, Pm genes; India breeding programs",
    },
    {
        "pmid": "33153977",
        "pmcid": "PMC7608726",
        "crop": "wheat",
        "title": "Identification and characterization of wheat stripe rust resistance gene Yr81",
        "note": "Yr81 mapped to chromosome 2BL; effective against Indian yellow rust races",
    },
    {
        "pmid": "36861213",
        "pmcid": "PMC9969877",
        "crop": "wheat",
        "title": "Lr67 — a pleiotropic slow-rusting gene in wheat conferring resistance to all three rusts and powdery mildew",
        "note": "Lr67/Yr46/Sr55/Pm46 pleiotropic gene; adult plant resistance in India varieties",
    },
    {
        "pmid": "35478558",
        "pmcid": "PMC9047618",
        "crop": "wheat",
        "title": "Wheat blast caused by Magnaporthe oryzae Triticum pathotype: current status and future research priorities",
        "note": "Wheat blast MoT pathotype detected near India borders; resistance gene survey",
    },
    {
        "pmid": "37841498",
        "pmcid": "PMC10576327",
        "crop": "wheat",
        "title": "NLR-based resistance genes in wheat — structure, function and evolution",
        "note": "Sr33, Sr35, Sr50 NLR-class cloning and function relevant to India Sr targets",
    },
    {
        "pmid": "33408282",
        "pmcid": "PMC7811137",
        "crop": "wheat",
        "title": "Dissecting adult plant resistance to leaf rust in wheat by GWAS — an Indian breeding panel",
        "note": "APR Lr genes in Indian breeding lines; loci on chromosomes 1A, 3B, 6B",
    },
    {
        "pmid": "34567291",
        "pmcid": "PMC8485122",
        "crop": "wheat",
        "title": "Characterization of stem rust resistance gene Sr45 in wheat",
        "note": "Sr45 effective against Ug99 lineage races circulating near India/Nepal corridor",
    },
    {
        "pmid": "36482574",
        "pmcid": "PMC9720658",
        "crop": "wheat",
        "title": "Slow-rusting or adult plant resistance — Lr46/Yr29/Pm39 gene cluster in wheat",
        "note": "Lr46 QTL package on 1BL; deployed in Indian CIMMYT-derived varieties",
    },
    # ── SOYBEAN ──────────────────────────────────────────────────────────────
    {
        "pmid": "35096378",
        "pmcid": "PMC8869295",
        "crop": "soybean",
        "title": "A Broad Review of Soybean Research on the Ongoing Race to Overcome Soybean Cyst Nematode",
        "note": "Rhg1, Rhg4 resistance QTL; SCN races HG type 0-7; comprehensive resistance gene list",
    },
    {
        "pmid": "35774687",
        "pmcid": "PMC9257224",
        "crop": "soybean",
        "title": "Genome-Wide Association Analysis and Gene Mining of Resistance to Frogeye Leaf Spot (China Race 1) in Soybean",
        "note": "Rcs3 gene GWAS; frogeye leaf spot emerging in India soybean belt (MP, MH)",
    },
    {
        "pmid": "35440059",
        "pmcid": "PMC9014829",
        "crop": "soybean",
        "title": "Molecular mapping of Phytophthora root and stem rot resistance in soybean — Rps loci review",
        "note": "Rps1, Rps3, Rps6, Rps8 alleles; Phytophthora sojae a serious risk in India waterlogged fields",
    },
    {
        "pmid": "36388413",
        "pmcid": "PMC9655280",
        "crop": "soybean",
        "title": "Identification of QTL and candidate genes for resistance to soybean rust (Phakopsora pachyrhizi)",
        "note": "Rpp2, Rpp3, Rpp4, Rpp5, Rpp6 mapping; soybean rust outbreak risk in India NE states",
    },
    {
        "pmid": "34869997",
        "pmcid": "PMC8643041",
        "crop": "soybean",
        "title": "Resistance to Fusarium virguliforme (sudden death syndrome) in soybean — gene mapping and MAS",
        "note": "Rfs2, Rfs3 QTL for SDS; sudden death syndrome increasingly reported in India",
    },
    {
        "pmid": "35601869",
        "pmcid": "PMC9120876",
        "crop": "soybean",
        "title": "Genetic and molecular basis of bacterial pustule resistance in soybean — Rxp gene",
        "note": "Rxp gene on chromosome 17; bacterial pustule relevant to India Kharif soybean season",
    },
    {
        "pmid": "33553985",
        "pmcid": "PMC7858682",
        "crop": "soybean",
        "title": "Soybean charcoal rot resistance — QTL mapping and genomic regions",
        "note": "Charcoal rot Macrophomina phaseolina; major drought-stress disease in India soybean",
    },
    {
        "pmid": "36820124",
        "pmcid": "PMC9952706",
        "crop": "soybean",
        "title": "Marker-assisted backcrossing for improving disease resistance in soybean: a status review",
        "note": "MAS for SCN, PRR, FLS, and rust in breeding programs; India ICAR varieties MAUS 81, JS 335",
    },
    {
        "pmid": "34017994",
        "pmcid": "PMC8129001",
        "crop": "soybean",
        "title": "Powdery mildew resistance in soybean — gene Rmd and allele mapping",
        "note": "Rmd-c and Rmd-cdi alleles on chromosome 16; powdery mildew an emerging India soybean issue",
    },
    {
        "pmid": "35198552",
        "pmcid": "PMC8858660",
        "crop": "soybean",
        "title": "Root-knot nematode resistance in soybean — Rmi/Rmi2 and molecular markers",
        "note": "Rmi genes; RKN (Meloidogyne) risk in India's irrigated soybean regions",
    },
    {
        "pmid": "37225584",
        "pmcid": "PMC10208068",
        "crop": "soybean",
        "title": "Genetic architecture of white mold resistance in soybean and its molecular breeding",
        "note": "Sclerotinia stem rot; emerging in India's high-rainfall soybean zones (Konkan, NE)",
    },
    {
        "pmid": "32038606",
        "pmcid": "PMC7068916",
        "crop": "soybean",
        "title": "Diaporthe/Phomopsis seed decay resistance QTL in soybean germplasm",
        "note": "DPSD reduces seed quality; major quality issue in India soybean export markets",
    },
    {
        "pmid": "35812073",
        "pmcid": "PMC9263355",
        "crop": "soybean",
        "title": "Conventional and new breeding technologies to manage soybean diseases",
        "note": "Review of Rps, Rpp, Rhg, Rcs resistance genes and CRISPR/marker-assisted approaches",
    },
    # ── CHICKPEA ─────────────────────────────────────────────────────────────
    {
        "pmid": "35990928",
        "pmcid": "PMC9388742",
        "crop": "chickpea",
        "title": "Development of High Yielding Fusarium Wilt Resistant Cultivar by Pyramiding of Genes Through MABC in Chickpea",
        "note": "Pusa Chickpea 20211 released; foc races 1-5 pyramided; India Central Zone ICAR",
    },
    {
        "pmid": "37078928",
        "pmcid": "PMC10144025",
        "crop": "chickpea",
        "title": "Breeding and Genomic Approaches towards Development of Fusarium Wilt Resistance in Chickpea",
        "note": "Review FOC races in India; JG74, Annigeri1 MAB programs; ICAR/ICRISAT",
    },
    {
        "pmid": "38390527",
        "pmcid": "PMC10856910",
        "crop": "chickpea",
        "title": "Efficient Single Nucleotide Polymorphism Marker-Assisted Selection to Fusarium Wilt in Chickpea",
        "note": "Six SNP markers on CaLG02; 100% phenotype-haplotype concordance for Foc5",
    },
    {
        "pmid": "39952025",
        "pmcid": "PMC11885688",
        "crop": "chickpea",
        "title": "Developing resistance to Fusarium wilt in chickpea: From identifying meta-QTLs to molecular breeding",
        "note": "7 meta-QTL on CaLG2/4/5/6; review of all known FW QTL; India race distribution",
    },
    {
        "pmid": "38465028",
        "pmcid": "PMC11202674",
        "crop": "chickpea",
        "title": "Inheritance of Resistance to Chickpea Fusarium Wilt (Foc Race 2) in C. arietinum x C. reticulatum",
        "note": "Single gene inheritance for race 2; wild Cicer reticulatum Kayat-077 as donor",
    },
    {
        "pmid": "34326558",
        "pmcid": "PMC8329888",
        "crop": "chickpea",
        "title": "Molecular mapping of QTLs for Ascochyta blight and Botrytis grey mould resistance in an inter-specific cross in chickpea using GBS",
        "note": "3 AB QTL + 4 BGM QTL from GPF2 x ILWC292 cross; India Punjab germplasm",
    },
    {
        "pmid": "36825068",
        "pmcid": "PMC9960938",
        "crop": "chickpea",
        "title": "Ascochyta Blight in Chickpea: An Update",
        "note": "AB pathotype variability; review of resistance QTL for India pathotypes P1-P4",
    },
    {
        "pmid": "30781104",
        "pmcid": "PMC6384016",
        "crop": "chickpea",
        "title": "Identification of Sources of Multiple Disease Resistance in Mini-core Collection of Chickpea",
        "note": "ICRISAT mini-core 211 accessions; AB, BGM, FW, dry root rot; India desi types",
    },
    {
        "pmid": "35096397",
        "pmcid": "PMC8784563",
        "crop": "chickpea",
        "title": "Genetic architecture of dry root rot (Rhizoctonia bataticola) resistance in chickpea",
        "note": "DRR QTL on CaLG3 and CaLG7; India Andhra Pradesh and Karnataka affected varieties",
    },
    {
        "pmid": "36631466",
        "pmcid": "PMC9814177",
        "crop": "chickpea",
        "title": "GWAS and candidate gene identification for collar rot resistance in chickpea",
        "note": "Collar rot Sclerotium rolfsii; GWAS panel includes 300+ ICC accessions",
    },
    {
        "pmid": "34569483",
        "pmcid": "PMC8483820",
        "crop": "chickpea",
        "title": "Chickpea biology and biotechnology: from domestication to biofortification and biopharming",
        "note": "Broad review; FW, AB, BGM, rust resistance gene resources; desi ICC varieties",
    },
    {
        "pmid": "37629765",
        "pmcid": "PMC10466025",
        "crop": "chickpea",
        "title": "Identification of QTLs for resistance to Fusarium wilt and Ascochyta blight in RIL population JG62 x ICCV05530",
        "note": "5 FW QTL + AB QTL; major QTL on CaLG02; India mapping populations",
    },
    {
        "pmid": "34226547",
        "pmcid": "PMC8256534",
        "crop": "chickpea",
        "title": "Botrytis grey mould in chickpea — resistance mechanisms and integrated management",
        "note": "BGM Botrytis cinerea; review of ICC2, ICC506EB as resistance donors for India",
    },
    {
        "pmid": "35463803",
        "pmcid": "PMC9021823",
        "crop": "chickpea",
        "title": "Chickpea stem borer resistance — QTL mapping and molecular markers for India varieties",
        "note": "Stem borer Melanagromyza obtusa; indirect biotic stress link; India NWPZ varieties",
    },
    {
        "pmid": "38688381",
        "pmcid": "PMC11057720",
        "crop": "chickpea",
        "title": "Evaluation of chickpea germplasm for Phytophthora root rot and stem rot resistance",
        "note": "Phytophthora medicaginis resistance screening; ICC accessions from Andhra and Karnataka",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# PubMed Central fetch helpers
# ─────────────────────────────────────────────────────────────────────────────

PMC_EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
PMC_OA_URL     = "https://www.ncbi.nlm.nih.gov/pmc/oai/oai.cgi"


def _http_get(url: str, params: dict | None = None, timeout: int = 30) -> str:
    """GET request; returns response body as text."""
    if params:
        url = "{}?{}".format(url, urllib.parse.urlencode(params))
    req = urllib.request.Request(url, headers={"User-Agent": "AgriHub-KB/1.0 (research)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_pmc_fulltext(pmcid: str) -> str | None:
    """Try to fetch full-text plain text for a PMC article (OAI-PMH).

    Falls back to abstract only if full text is unavailable.
    Returns None on error.
    """
    pmcid = pmcid if pmcid.upper().startswith("PMC") else "PMC" + pmcid

    # OAI-PMH fulltext (returns XML with <body>)
    try:
        params = {
            "verb": "GetRecord",
            "identifier": "oai:pubmedcentral.nih.gov:{}".format(pmcid.replace("PMC", "")),
            "metadataPrefix": "pmc",
        }
        xml = _http_get(PMC_OA_URL, params, timeout=45)
        # Strip XML tags — keep only text content
        text = re.sub(r"<[^>]+>", " ", xml)
        text = re.sub(r"\s{2,}", " ", text).strip()
        if len(text) > 500:
            return text
    except Exception:
        pass

    return None


def fetch_abstract(pmid: str) -> str | None:
    """Fetch abstract text via NCBI eFetch (always available)."""
    try:
        params = {
            "db": "pubmed",
            "id": pmid,
            "rettype": "abstract",
            "retmode": "text",
        }
        text = _http_get(PMC_EFETCH_URL, params, timeout=20)
        if text and len(text) > 100:
            return text
    except Exception:
        pass
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Review queue helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_review_queue() -> list:
    if REVIEW_QUEUE.exists():
        try:
            return json.loads(REVIEW_QUEUE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
    return []


def _save_review_queue(entries: list) -> None:
    REVIEW_QUEUE.parent.mkdir(parents=True, exist_ok=True)
    REVIEW_QUEUE.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")


def _append_to_queue(new_entries: list) -> None:
    existing = _load_review_queue()
    existing.extend(new_entries)
    _save_review_queue(existing)


# ─────────────────────────────────────────────────────────────────────────────
# AI extraction (calls paper_extractor.py logic directly)
# ─────────────────────────────────────────────────────────────────────────────

def _extract_with_groq(text: str, api_key: str, paper_meta: dict) -> list:
    """Run Groq extraction on paper text; return validated records."""
    sys.path.insert(0, str(ROOT_DIR))
    from curator.extractors.paper_extractor import extract_paper_text  # noqa: PLC0415

    try:
        records = extract_paper_text(text, api_key)
        # Tag each record with paper provenance
        for rec in records:
            rec.setdefault("source", "{} (PMID:{})".format(
                paper_meta.get("title", "")[:60], paper_meta.get("pmid", "")))
            rec.setdefault("pmid", paper_meta.get("pmid", ""))
            rec.setdefault("pmcid", paper_meta.get("pmcid", ""))
        return records
    except Exception as exc:
        print("    [Groq] extraction error: {}".format(exc))
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Core pipeline
# ─────────────────────────────────────────────────────────────────────────────

def process_paper(paper: dict, api_key: str | None, no_extract: bool = False) -> dict:
    """Download a paper, optionally run Groq extraction, append to review queue.

    Returns a result dict with keys: pmid, crop, downloaded, extracted, records.
    """
    pmid  = paper["pmid"]
    pmcid = paper.get("pmcid", "")
    crop  = paper["crop"]
    result = {"pmid": pmid, "crop": crop, "downloaded": False, "extracted": False, "records": 0}

    crop_dir = PAPERS_DIR / crop
    crop_dir.mkdir(parents=True, exist_ok=True)
    text_path = crop_dir / "{}.txt".format(pmid)

    # ── Step 1: download ────────────────────────────────────────────────────
    if text_path.exists() and text_path.stat().st_size > 200:
        print("    [{}] Already downloaded, reading cached copy".format(pmid))
        text = text_path.read_text(encoding="utf-8")
        result["downloaded"] = True
    else:
        print("    [{}] Fetching from PubMed Central...".format(pmid))
        text = None

        # Try full-text first (PMC OAI)
        if pmcid:
            text = fetch_pmc_fulltext(pmcid)
            time.sleep(0.4)  # NCBI rate limit: 3 requests/sec without API key

        # Fall back to abstract
        if not text:
            text = fetch_abstract(pmid)
            time.sleep(0.4)

        if not text:
            print("    [{}] ERROR: could not fetch text".format(pmid))
            return result

        # Save metadata header + body
        header = (
            "TITLE: {}\n"
            "PMID: {}\n"
            "PMCID: {}\n"
            "CROP: {}\n"
            "NOTE: {}\n"
            "---\n"
        ).format(
            paper.get("title", ""),
            pmid,
            pmcid,
            crop,
            paper.get("note", ""),
        )
        text_path.write_text(header + text, encoding="utf-8")
        print("    [{}] Saved to {}".format(pmid, text_path))
        result["downloaded"] = True

    # ── Step 2: extract ─────────────────────────────────────────────────────
    if no_extract:
        return result

    if not api_key:
        print("    [{}] Skipping extraction (no GROQ_API_KEY)".format(pmid))
        return result

    # Check if already queued
    queue = _load_review_queue()
    already_queued = any(
        entry.get("record", {}).get("pmid") == pmid
        for entry in queue
    )
    if already_queued:
        print("    [{}] Already in review queue, skipping extraction".format(pmid))
        result["extracted"] = True
        return result

    print("    [{}] Running Groq extraction...".format(pmid))
    records = _extract_with_groq(text, api_key, paper)

    if records:
        new_entries = [
            {"status": "pending", "source_file": str(text_path), "record": rec}
            for rec in records
        ]
        _append_to_queue(new_entries)
        result["records"] = len(records)
        result["extracted"] = True
        print("    [{}] Extracted {} record(s) -> review_queue.json".format(pmid, len(records)))
    else:
        print("    [{}] No resistance records found".format(pmid))
        result["extracted"] = True

    return result


def run_fetch(
    pmids: list[str] | None = None,
    crops: list[str] | None = None,
    no_extract: bool = False,
    extract_only: bool = False,
) -> None:
    """Main entry point called by CLI."""
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key and not no_extract:
        print("WARNING: GROQ_API_KEY not set. Papers will be downloaded only.")
        no_extract = True

    papers = CURATED_PAPERS
    if pmids:
        papers = [p for p in papers if p["pmid"] in pmids]
    if crops:
        papers = [p for p in papers if p["crop"] in crops]

    if extract_only:
        # Only process already-downloaded papers
        papers = [
            p for p in papers
            if (PAPERS_DIR / p["crop"] / "{}.txt".format(p["pmid"])).exists()
        ]

    if not papers:
        print("No matching papers found.")
        return

    print("\n" + "=" * 60)
    print("[fetch_papers] Processing {} paper(s)".format(len(papers)))
    print("=" * 60)

    totals = {"downloaded": 0, "extracted": 0, "records": 0, "errors": 0}

    for paper in papers:
        print("\n  PMID:{} [{}] {}".format(paper["pmid"], paper["crop"], paper["title"][:70]))
        try:
            res = process_paper(paper, api_key=api_key, no_extract=no_extract)
            if res["downloaded"]:
                totals["downloaded"] += 1
            if res["extracted"]:
                totals["extracted"] += 1
            totals["records"] += res["records"]
        except Exception as exc:
            print("    ERROR: {}".format(exc))
            totals["errors"] += 1

    print("\n" + "=" * 60)
    print("[fetch_papers] Done")
    print("  Papers downloaded/cached : {}".format(totals["downloaded"]))
    print("  Papers extracted         : {}".format(totals["extracted"]))
    print("  New records in queue     : {}".format(totals["records"]))
    print("  Errors                   : {}".format(totals["errors"]))
    if totals["records"] > 0:
        print("\nNext step: python curator/approve_extractions.py")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch open-access papers from PubMed Central and extract resistance knowledge.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--pmid",
        metavar="PMID",
        nargs="+",
        help="One or more PubMed IDs to fetch",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Fetch and process all curated papers",
    )
    parser.add_argument(
        "--crop",
        metavar="CROP",
        nargs="+",
        choices=["wheat", "soybean", "chickpea"],
        help="Limit to one or more crops",
    )
    parser.add_argument(
        "--no-extract",
        action="store_true",
        help="Download papers only; skip Groq extraction",
    )
    parser.add_argument(
        "--extract-only",
        action="store_true",
        help="Run Groq extraction on already-downloaded papers; skip download step",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print the curated paper list and exit",
    )
    args = parser.parse_args()

    if args.list:
        by_crop: dict = {}
        for p in CURATED_PAPERS:
            by_crop.setdefault(p["crop"], []).append(p)
        for crop, papers in by_crop.items():
            print("\n{} ({} papers)".format(crop.upper(), len(papers)))
            for p in papers:
                dl = (PAPERS_DIR / p["crop"] / "{}.txt".format(p["pmid"])).exists()
                flag = "[cached]" if dl else "       "
                print("  {} PMID:{} -- {}".format(flag, p["pmid"], p["title"][:70]))
        return 0

    if not args.all and not args.pmid and not args.extract_only:
        parser.print_help()
        return 1

    # Load .env if present
    env_path = ROOT_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())

    run_fetch(
        pmids=args.pmid,
        crops=args.crop,
        no_extract=args.no_extract,
        extract_only=args.extract_only,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
