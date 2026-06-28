"""Integration helper: parse GFF3 with chromosome mappings from assembly reports."""

from __future__ import annotations

from pathlib import Path

from curator.parsers.assembly_parser import parse_assembly_report


def load_chromosome_mappings(assembly_report_path: str | Path) -> dict[str, dict]:
    """
    Load chromosome mappings from an assembly report file.

    Args:
        assembly_report_path: Path to the assembly report file

    Returns:
        Dict mapping both sequence names and RefSeq accessions to chromosome metadata
    """
    metadata, mappings = parse_assembly_report(assembly_report_path)
    
    result = {}
    for mapping in mappings:
        # Map by sequence name
        result[mapping.sequence_name] = {
            "assigned_molecule": mapping.assigned_molecule,
            "genbank_accn": mapping.genbank_accn,
            "refseq_accn": mapping.refseq_accn,
            "sequence_length": mapping.sequence_length,
            "sequence_role": mapping.sequence_role,
        }
        
        # Also map by RefSeq accession for GFF3 files that use RefSeq accessions
        if mapping.refseq_accn and mapping.refseq_accn != "na":
            result[mapping.refseq_accn] = result[mapping.sequence_name]
        
        # Also map by GenBank accession as fallback
        if mapping.genbank_accn and mapping.genbank_accn != "na":
            result[mapping.genbank_accn] = result[mapping.sequence_name]
    
    return result


def map_gene_to_human_chromosome(
    gene_chromosome_id: str,
    chromosome_mappings: dict[str, dict],
) -> str:
    """
    Translate a gene's sequence ID (from GFF) to human-readable chromosome label.

    Args:
        gene_chromosome_id: The sequence/chromosome ID from the GFF file (e.g., "NC_...")
        chromosome_mappings: Dict from load_chromosome_mappings()

    Returns:
        Human-readable chromosome label, or original ID if not found in mappings
    """
    if gene_chromosome_id in chromosome_mappings:
        return chromosome_mappings[gene_chromosome_id]["assigned_molecule"]
    
    # Fallback: return original ID if not in mappings
    return gene_chromosome_id
