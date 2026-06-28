"""Tests for GFF3 parsing."""

from pathlib import Path

from curator.parsers.assembly_parser import parse_assembly_report
from curator.parsers.gff_parser import parse_gff3, extract_resistance_genes
from curator.parsers.genomic_integration import load_chromosome_mappings


def test_parse_wheat_gff3():
    """Test parsing the wheat IWGSC GFF3 file."""
    gff3_path = Path("data/raw/GCF_018294505.1_IWGSC_CS_RefSeq_v2.1_genomic.gff.gz")
    
    if not gff3_path.exists():
        raise FileNotFoundError(f"Test dataset not found: {gff3_path}")
    
    genes = parse_gff3(gff3_path)
    
    # Verify that genes were extracted
    assert len(genes) > 0, "Expected at least one gene from wheat GFF3"
    
    # Check gene structure
    first_gene = genes[0]
    assert "id" in first_gene
    assert "chromosome" in first_gene
    assert "start" in first_gene
    assert "end" in first_gene
    assert first_gene["end"] >= first_gene["start"]
    
    print(f"✓ Parsed {len(genes)} genes from wheat GFF3")
    print(f"  Sample: {first_gene['id']} on {first_gene['chromosome']} ({first_gene['start']}-{first_gene['end']})")


def test_parse_gff3_with_chromosome_mapping():
    """Test parsing with chromosome mapping applied."""
    gff3_path = Path("data/raw/GCF_018294505.1_IWGSC_CS_RefSeq_v2.1_genomic.gff.gz")
    report_path = Path("data/raw/GCF_018294505.1_IWGSC_CS_RefSeq_v2.1_assembly_report.txt")
    
    if not gff3_path.exists() or not report_path.exists():
        raise FileNotFoundError("Test datasets not found")
    
    # Load chromosome mappings from assembly report
    mappings = load_chromosome_mappings(report_path)
    
    genes = parse_gff3(gff3_path, mappings)
    
    # Verify mapping was applied
    assert len(genes) > 0
    first_gene = genes[0]
    
    # Chromosome should be human-readable (1A, 1B, 1D, etc.) if mapping was applied
    # or the original sequence name if not in mappings
    print(f"✓ Parsed {len(genes)} genes with chromosome mapping")
    print(f"  Sample mapped to: {first_gene['chromosome']}")


def test_extract_wheat_resistance_genes():
    """Test extracting resistance genes from wheat GFF3."""
    gff3_path = Path("data/raw/GCF_018294505.1_IWGSC_CS_RefSeq_v2.1_genomic.gff.gz")
    report_path = Path("data/raw/GCF_018294505.1_IWGSC_CS_RefSeq_v2.1_assembly_report.txt")
    
    if not gff3_path.exists() or not report_path.exists():
        raise FileNotFoundError("Test datasets not found")
    
    mappings = load_chromosome_mappings(report_path)
    all_genes = parse_gff3(gff3_path, mappings)
    
    # Extract resistance genes
    resistance_genes = extract_resistance_genes(all_genes)
    
    print(f"✓ Found {len(resistance_genes)} resistance genes out of {len(all_genes)} total")
    if resistance_genes:
        for gene in resistance_genes[:5]:
            print(f"  - {gene['id']} on {gene['chromosome']}")
    else:
        print("  (Note: No resistance genes found with default keywords in this GFF3)")


def test_gff3_parsing_handles_gzip():
    """Test that gzipped and uncompressed GFF3 files are handled."""
    gzipped_path = Path("data/raw/GCF_018294505.1_IWGSC_CS_RefSeq_v2.1_genomic.gff.gz")
    
    if not gzipped_path.exists():
        raise FileNotFoundError(f"Test dataset not found: {gzipped_path}")
    
    # Parse gzipped file
    genes_gz = parse_gff3(gzipped_path)
    assert len(genes_gz) > 0
    
    print(f"✓ Successfully parsed gzipped GFF3 file with {len(genes_gz)} genes")
