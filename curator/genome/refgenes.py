"""Reference-gene extraction and NLR/RLK domain classification (RESEARCH_ROADMAP.md Phase 4,
tasks 4.1-4.2).

Deliberately a new, self-contained module rather than an edit to curator/parsers/ -- those files
(and the rest of the pre-Postgres pipeline: db.py, run_pipeline.py, load_genes.py, etc.) are
Neo4j-era and are being reviewed for removal in a separate cleanup pass; this module has no
dependency on any of them, so the two pieces of work can't collide.

InterPro domain accessions used for NLR/RLK classification were each verified individually against
the InterPro API (https://www.ebi.ac.uk/interpro/api/entry/interpro/<ACCESSION>/) on 2026-09-26,
not typed from memory:
    IPR002182  NB-ARC domain                                  (core NLR marker)
    IPR000157  Toll/interleukin-1 receptor homology (TIR)      (-> TNL)
    IPR008808  Powdery mildew resistance protein, RPW8 domain  (-> RNL)
    IPR000719  Protein kinase domain                           (RLK, combined with LRR)
    IPR001611, IPR003591, IPR011713, IPR013210  Leucine-rich repeat family domains

Coverage note, same honesty standard as the rest of this project: only chickpea (LIS/JGI GFF3) and
soybean (Phytozome GFF3) carry InterPro/PANTHER Dbxrefs directly on their gene features, so only
those two get a real, domain-based is_nlr/nlr_class. The wheat GFF (NCBI RefSeq) has no functional
domain annotations at all -- only a free-text `description` -- so wheat genes are loaded with
structural data (position, strand, description) but is_nlr is left False for all of them rather
than guessed from a keyword match on that free text. Getting wheat's NLR classification right
needs a real InterProScan run against the wheat proteome, which hasn't been done.
"""

from __future__ import annotations

import gzip
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Literal
from urllib.parse import unquote

NLR_CORE_DOMAINS = {"IPR002182"}  # NB-ARC
TIR_DOMAINS = {"IPR000157"}
RPW8_DOMAINS = {"IPR008808"}
KINASE_DOMAINS = {"IPR000719"}
LRR_DOMAINS = {"IPR000372", "IPR001611", "IPR003591", "IPR006553", "IPR011713", "IPR013210"}

NlrClass = Literal["CNL", "TNL", "RNL", "NL", "RLK", "RLP"]


@dataclass(frozen=True)
class RefGeneRecord:
    locus_id: str
    crop: str
    assembly: str
    chromosome: str
    start_bp: int
    end_bp: int
    strand: str
    description: str | None
    domains: tuple[str, ...] = field(default_factory=tuple)
    is_nlr: bool = False
    nlr_class: NlrClass | None = None


def parse_ncbi_assembly_report(path: str | Path) -> dict[str, str]:
    """RefSeq accession (column 7) -> assigned chromosome label (column 3), from an NCBI
    assembly_report.txt. Skips the header block (lines starting with '#')."""
    mapping: dict[str, str] = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        assigned_molecule, refseq_accn = parts[2].strip(), parts[6].strip()
        if refseq_accn and refseq_accn != "na":
            mapping[refseq_accn] = assigned_molecule
    return mapping


def _parse_attributes(field_text: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for part in field_text.split(";"):
        if "=" not in part:
            continue
        key, _, value = part.partition("=")
        attrs[key.strip()] = unquote(value.strip())
    return attrs


def _classify_domains(dbxref_ids: set[str]) -> tuple[bool, NlrClass | None]:
    has_nb_arc = bool(dbxref_ids & NLR_CORE_DOMAINS)
    has_tir = bool(dbxref_ids & TIR_DOMAINS)
    has_rpw8 = bool(dbxref_ids & RPW8_DOMAINS)
    has_kinase = bool(dbxref_ids & KINASE_DOMAINS)
    has_lrr = bool(dbxref_ids & LRR_DOMAINS)

    if has_nb_arc:
        if has_tir:
            return True, "TNL"
        if has_rpw8:
            return True, "RNL"
        return True, "NL"  # NB-ARC present but no TIR/RPW8 signal -- can't call CNL without a
        # coiled-coil-specific domain hit, which InterPro doesn't mark as cleanly as TIR/RPW8.
    if has_kinase and has_lrr:
        return True, "RLK"
    if has_lrr and not has_kinase:
        # LRR without a kinase domain is a weak, common-false-positive signal on its own (huge
        # numbers of plant LRR proteins are not disease-resistance genes at all) -- not flagged.
        return False, None
    return False, None


def stream_ref_genes(
    gff_path: str | Path,
    *,
    crop: str,
    assembly: str,
    chromosome_map: dict[str, str] | None = None,
    classify_domains: bool = True,
) -> Iterator[RefGeneRecord]:
    """Stream `gene` features out of a GFF3/GFF file as RefGeneRecord, one at a time -- does not
    load the whole file into memory (RESEARCH_ROADMAP.md task 4.1)."""
    path = Path(gff_path)
    opener = gzip.open if path.suffix == ".gz" else open

    with opener(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if not line or line[0] == "#":
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 9 or parts[2] != "gene":
                continue

            seqname, start, end, strand, attr_text = parts[0], parts[3], parts[4], parts[6], parts[8]
            attrs = _parse_attributes(attr_text)
            locus_id = attrs.get("ID", "").split(":")[-1]
            if not locus_id:
                continue

            dbxref_raw = attrs.get("Dbxref", "")
            dbxref_ids = tuple(sorted(d.strip() for d in dbxref_raw.split(",") if d.strip()))
            interpro_ids = {d.split(":", 1)[1] for d in dbxref_ids if d.startswith("InterPro:")}

            is_nlr, nlr_class = (False, None)
            if classify_domains and interpro_ids:
                is_nlr, nlr_class = _classify_domains(interpro_ids)

            chromosome = (chromosome_map or {}).get(seqname, seqname)
            description = attrs.get("Note") or attrs.get("description")

            yield RefGeneRecord(
                locus_id=locus_id,
                crop=crop,
                assembly=assembly,
                chromosome=chromosome,
                start_bp=int(start),
                end_bp=int(end),
                strand=strand if strand in ("+", "-") else ".",
                description=description,
                domains=dbxref_ids,
                is_nlr=is_nlr,
                nlr_class=nlr_class,
            )
