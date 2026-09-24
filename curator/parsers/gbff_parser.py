"""Parse GenBank Flat File (GBFF) format gene annotations.

Handles standard GBFF annotation records where gene features appear as
5-space-indented entries inside FEATURES sections.

Two common GBFF record types are handled:
  CON  (contig assembly) — chromosome-level assembly records; contain only
       scaffold structure (assembly_gap features) and NO gene features.
  PLN/BCT/VRL/... — annotated sequence records; MAY contain gene features.

If the file has no gene features after a full scan, GBFFFormatError is raised
with a descriptive message rather than silently returning an empty list.

For chickpea ICC4958 (GCA_000347275.4) the NCBI-distributed .gbff.gz file
contains CON chromosomes + 30,393 unannotated WGS contigs — zero gene
features exist anywhere in the file. Gene annotations must be obtained from:
  Ensembl Plants : https://plants.ensembl.org/Cicer_arietinum
    -> Downloads -> Gene sets -> GFF3
  LIS CiceBase   : https://www.legumeinfo.org/data/v2/Cicer/arietinum/
    -> annotations -> *.gene_models_main.gff3.gz
"""

from __future__ import annotations

import gzip
import re
from pathlib import Path


class GBFFFormatError(ValueError):
    """Raised when a GBFF file cannot provide gene annotations."""


def _open_gbff(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open("r", encoding="utf-8", errors="replace")


def _parse_location(location: str) -> tuple[int, int, str]:
    """Extract (start, end, strand) from a GenBank location string."""
    strand = "-" if location.startswith("complement") else "+"
    numbers = [int(n) for n in re.findall(r"\d+", location)]
    if not numbers:
        return 0, 0, strand
    return min(numbers), max(numbers), strand


def parse_gbff(
    path: str | Path,
    chromosome_mappings: dict | None = None,
) -> list[dict]:
    """Parse a GBFF annotation file and return gene records.

    Returns dicts with keys matching parse_gff3() output:
      id, name, chromosome, start, end, strand, length

    Raises:
        FileNotFoundError: if the file does not exist.
        GBFFFormatError:   if the file contains no gene features (e.g. the
                           file is a CON assembly record or unannotated WGS).
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"GBFF file not found: {path}")

    genes: list[dict] = []
    con_records = 0
    annotated_records = 0
    unannotated_records = 0
    had_gene_in_current = False

    current_locus: str = ""
    current_chromosome: str = ""
    in_features = False
    in_gene = False
    gene_location = ""
    gene_attrs: dict = {}

    def _flush_gene() -> None:
        if not gene_location:
            return
        locus_tag = gene_attrs.get("locus_tag", "")
        gene_name = gene_attrs.get("gene", locus_tag)
        gene_id = locus_tag or gene_name
        if not gene_id:
            return
        start, end, strand = _parse_location(gene_location)
        if start == 0 and end == 0:
            return
        chrom = current_chromosome or current_locus
        if chromosome_mappings and current_locus in chromosome_mappings:
            m = chromosome_mappings[current_locus]
            chrom = (
                m.get("assigned_molecule") or chrom
                if isinstance(m, dict)
                else getattr(m, "assigned_molecule", chrom)
            )
        genes.append({
            "id": gene_id,
            "name": gene_name,
            "seqname": current_locus,
            "chromosome": chrom,
            "start": start,
            "end": end,
            "strand": strand,
            "length": end - start + 1,
        })

    with _open_gbff(path) as fh:
        for raw_line in fh:
            line = raw_line.rstrip("\n")

            # ── New LOCUS record ──────────────────────────────────────────────
            if line.startswith("LOCUS ") or line.startswith("LOCUS\t"):
                if in_gene:
                    _flush_gene()
                # Tally previous record
                if current_locus:
                    if had_gene_in_current:
                        annotated_records += 1
                    elif "CON" in (line.split()[6:8] if len(line.split()) > 6 else []):
                        con_records += 1
                    else:
                        unannotated_records += 1

                in_gene = False
                in_features = False
                gene_location = ""
                gene_attrs = {}
                current_chromosome = ""
                had_gene_in_current = False

                parts = line.split()
                current_locus = parts[1] if len(parts) > 1 else ""
                division = parts[6] if len(parts) >= 7 else ""
                if division == "CON":
                    con_records += 1
                    current_locus = f"__CON__{current_locus}"  # mark so we skip
                continue

            if current_locus.startswith("__CON__"):
                continue  # skip body of CON records entirely

            # ── FEATURES block ────────────────────────────────────────────────
            if line.startswith("FEATURES"):
                in_features = True
                continue

            if line.startswith("ORIGIN") or line == "//":
                if in_gene:
                    _flush_gene()
                    in_gene = False
                    gene_location = ""
                    gene_attrs = {}
                in_features = False
                continue

            if not in_features:
                continue

            # ── Feature key line: 5-space indent + type ───────────────────────
            if re.match(r"^     \S", line):
                if in_gene:
                    _flush_gene()
                    in_gene = False
                    gene_location = ""
                    gene_attrs = {}

                feat_match = re.match(r"^     (\w+)\s+(\S+)", line)
                if feat_match and feat_match.group(1) == "gene":
                    in_gene = True
                    had_gene_in_current = True
                    gene_location = feat_match.group(2)
                    gene_attrs = {}
                continue

            # ── Qualifier: 21-space indent (/key="value") ─────────────────────
            if line.startswith("                     /"):
                qual_match = re.match(
                    r'^                     /(\w+)=?"?([^"\n]*)"?\s*$', line
                )
                if qual_match:
                    key, val = qual_match.group(1), qual_match.group(2).strip()
                    if key == "chromosome":
                        current_chromosome = val
                    elif in_gene and key in ("locus_tag", "gene"):
                        gene_attrs[key] = val
                continue

            # ── Wrapped location continuation ─────────────────────────────────
            if (
                in_gene
                and line.startswith("                     ")
                and not line.startswith("                     /")
            ):
                gene_location += line.strip()

    # Final flush + tally last record
    if in_gene:
        _flush_gene()
    if current_locus and not current_locus.startswith("__CON__"):
        if had_gene_in_current:
            annotated_records += 1
        else:
            unannotated_records += 1

    # ── Raise clear error if no genes found ───────────────────────────────────
    if len(genes) == 0:
        detail = (
            f"CON assembly records: {con_records}, "
            f"annotated records: {annotated_records}, "
            f"unannotated WGS records: {unannotated_records}"
        )
        if con_records > 0 and annotated_records == 0:
            raise GBFFFormatError(
                f"No gene features found in {path.name} ({detail}).\n"
                "This file contains only CON/WGS assembly records with no gene "
                "annotation.\n\n"
                "For chickpea ICC4958 gene annotations, download a GFF3 from:\n"
                "  Ensembl Plants : https://plants.ensembl.org/Cicer_arietinum\n"
                "    -> Downloads -> Gene sets -> GFF3\n"
                "  LIS CiceBase   : https://www.legumeinfo.org/data/v2/Cicer/arietinum/"
            )
        raise GBFFFormatError(
            f"No gene features found in {path.name} ({detail}).\n"
            "The file may be empty, corrupted, or use an unsupported annotation format."
        )

    return genes
