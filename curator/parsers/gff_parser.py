"""Parse GFF3 files into a compact gene JSON representation."""

from __future__ import annotations

import gzip
from pathlib import Path
from typing import Iterator

from curator.parsers.assembly_parser import ChromosomeMapping


def _open_gff3(path: str | Path):
    """Open a GFF3 file, handling gzip compression if needed."""
    path = Path(path)
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    else:
        return path.open("r", encoding="utf-8")


def parse_gff3(
    path: str | Path,
    chromosome_mappings: dict[str, ChromosomeMapping] | None = None,
) -> list[dict]:
    """
    Parse a GFF3 file and extract gene models with optional chromosome mapping.

    Args:
        path: Path to the GFF3 file (may be gzipped)
        chromosome_mappings: Dict mapping sequence names to ChromosomeMapping objects
                            for translating local sequence IDs to human-readable chromosome labels

    Returns:
        List of gene dictionaries with id, chromosome, start, end, strand, and optional mapped_chromosome
    """
    path = Path(path)
    genes = []
    
    if not path.exists():
        raise FileNotFoundError(f"GFF3 file not found: {path}")
    
    try:
        with _open_gff3(path) as f:
            for line in f:
                line = line.strip()
                
                # Skip comments and empty lines
                if not line or line.startswith("#"):
                    continue
                
                parts = line.split("\t")
                if len(parts) < 9:
                    continue
                
                seqname = parts[0]
                feature_type = parts[2]
                start = parts[3]
                end = parts[4]
                strand = parts[6]
                attributes = parts[8]
                
                # Only extract genes (not exons, CDS, etc.)
                if feature_type != "gene":
                    continue
                
                # Extract gene ID and name from attributes
                gene_id = None
                gene_name = None
                
                for attr in attributes.split(";"):
                    attr = attr.strip()
                    if attr.startswith("ID="):
                        gene_id = attr[3:].split(":")[0]  # Remove version if present
                    elif attr.startswith("Name="):
                        gene_name = attr[5:]
                
                if not gene_id:
                    continue
                
                # Map chromosome ID to human-readable label if mappings provided
                mapped_chromosome = seqname
                if chromosome_mappings and seqname in chromosome_mappings:
                    mapping_data = chromosome_mappings[seqname]
                    # Handle both ChromosomeMapping objects and dict representations
                    if isinstance(mapping_data, dict):
                        mapped_chromosome = mapping_data.get("assigned_molecule", seqname)
                    else:
                        mapped_chromosome = mapping_data.assigned_molecule
                
                gene_record = {
                    "id": gene_id,
                    "name": gene_name or gene_id,
                    "seqname": seqname,
                    "chromosome": mapped_chromosome,
                    "start": int(start),
                    "end": int(end),
                    "strand": strand,
                    "length": int(end) - int(start) + 1,
                }
                
                genes.append(gene_record)
    
    except Exception as e:
        raise ValueError(f"Error parsing GFF3 file {path}: {e}") from e
    
    return genes


def extract_resistance_genes(genes: list[dict], resistance_keywords: list[str] | None = None) -> list[dict]:
    """
    Filter genes that might be resistance genes based on name/ID keywords.
    
    Args:
        genes: List of gene records from parse_gff3()
        resistance_keywords: Keywords to match (e.g., ["Sr", "Yr", "Lr", "Pm", "Fhb"])
    
    Returns:
        Filtered list of genes matching resistance gene patterns
    """
    if resistance_keywords is None:
        # Default wheat resistance gene patterns
        resistance_keywords = ["Sr", "Yr", "Lr", "Pm", "Fhb", "Rpg", "Wsm", "Sb"]
    
    resistance_genes = []
    for gene in genes:
        gene_id = gene["id"].upper()
        gene_name = gene.get("name", "").upper()
        
        # Check if any keyword matches
        for keyword in resistance_keywords:
            if keyword.upper() in gene_id or keyword.upper() in gene_name:
                resistance_genes.append(gene)
                break
    
    return resistance_genes
