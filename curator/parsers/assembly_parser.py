"""Parse NCBI assembly report files to extract chromosome metadata and sequence mappings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ChromosomeMapping:
    """Represents a sequence-to-chromosome mapping from an NCBI assembly report."""

    sequence_name: str
    sequence_role: str
    assigned_molecule: str
    genbank_accn: str
    sequence_length: int
    refseq_accn: str | None = None


@dataclass(frozen=True)
class AssemblyMetadata:
    """Metadata from an NCBI assembly report header."""

    assembly_name: str
    organism_name: str
    cultivar: str
    taxid: int
    bioproject: str
    genbank_accession: str
    refseq_accession: str | None = None


def parse_assembly_report(path: str | Path) -> tuple[AssemblyMetadata, list[ChromosomeMapping]]:
    """
    Parse an NCBI assembly report file and extract metadata and chromosome mappings.

    Args:
        path: Path to the assembly report (.txt) file

    Returns:
        Tuple of (AssemblyMetadata, list of ChromosomeMapping)
    """
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        lines = f.readlines()

    metadata_dict = {}
    mappings = []
    in_sequence_section = False

    for line in lines:
        line = line.rstrip("\n")

        # Parse header metadata
        if line.startswith("# ") and not in_sequence_section:
            if line.startswith("# Assembly name:"):
                metadata_dict["assembly_name"] = line.split(":", 1)[1].strip()
            elif line.startswith("# Organism name:"):
                metadata_dict["organism_name"] = line.split(":", 1)[1].strip()
            elif line.startswith("# Infraspecific name:"):
                # Extract cultivar from "cultivar=..." format
                infraspecific = line.split(":", 1)[1].strip()
                if "cultivar=" in infraspecific:
                    metadata_dict["cultivar"] = infraspecific.split("cultivar=")[1].strip()
            elif line.startswith("# Taxid:"):
                metadata_dict["taxid"] = int(line.split(":", 1)[1].strip())
            elif line.startswith("# BioProject:"):
                metadata_dict["bioproject"] = line.split(":", 1)[1].strip()
            elif line.startswith("# GenBank assembly accession:"):
                metadata_dict["genbank_accession"] = line.split(":", 1)[1].strip()
            elif line.startswith("# RefSeq assembly accession:"):
                metadata_dict["refseq_accession"] = line.split(":", 1)[1].strip()
            elif line.startswith("# Sequence-Name"):
                in_sequence_section = True

        # Parse sequence mapping section
        elif in_sequence_section and line and not line.startswith("#"):
            parts = line.split("\t")
            if len(parts) >= 8:
                try:
                    mapping = ChromosomeMapping(
                        sequence_name=parts[0].strip(),
                        sequence_role=parts[1].strip(),
                        assigned_molecule=parts[2].strip(),
                        genbank_accn=parts[4].strip(),
                        sequence_length=int(parts[8].strip()),
                        refseq_accn=parts[6].strip() if parts[6].strip() != "na" else None,
                    )
                    mappings.append(mapping)
                except (IndexError, ValueError):
                    # Skip malformed lines
                    continue

    metadata = AssemblyMetadata(
        assembly_name=metadata_dict.get("assembly_name", ""),
        organism_name=metadata_dict.get("organism_name", ""),
        cultivar=metadata_dict.get("cultivar", ""),
        taxid=metadata_dict.get("taxid", 0),
        bioproject=metadata_dict.get("bioproject", ""),
        genbank_accession=metadata_dict.get("genbank_accession", ""),
        refseq_accession=metadata_dict.get("refseq_accession"),
    )

    return metadata, mappings
