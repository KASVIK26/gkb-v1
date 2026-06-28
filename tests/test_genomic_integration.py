"""Integration tests for chromosome mapping and GFF parsing."""

from pathlib import Path

from curator.parsers.genomic_integration import load_chromosome_mappings, map_gene_to_human_chromosome


def test_load_wheat_chromosome_mappings():
    """Test loading wheat chromosome mappings."""
    report_path = Path("data/raw/GCF_018294505.1_IWGSC_CS_RefSeq_v2.1_assembly_report.txt")
    
    if not report_path.exists():
        raise FileNotFoundError(f"Test dataset not found: {report_path}")
    
    mappings = load_chromosome_mappings(report_path)
    
    # Verify that we have mappings
    assert len(mappings) > 0
    
    # Each mapping should have the required metadata
    for seq_name, mapping_data in list(mappings.items())[:3]:
        assert "assigned_molecule" in mapping_data
        assert "sequence_length" in mapping_data
        print(f"Wheat: {seq_name} -> {mapping_data['assigned_molecule']} ({mapping_data['sequence_length']} bp)")


def test_load_chickpea_chromosome_mappings():
    """Test loading chickpea chromosome mappings."""
    report_path = Path("data/raw/GCA_000347275.4_ASM34727v4_assembly_report.txt")
    
    if not report_path.exists():
        raise FileNotFoundError(f"Test dataset not found: {report_path}")
    
    mappings = load_chromosome_mappings(report_path)
    
    # Verify that we have mappings
    assert len(mappings) > 0
    
    # Each mapping should have the required metadata
    for seq_name, mapping_data in list(mappings.items())[:3]:
        assert "assigned_molecule" in mapping_data
        assert "sequence_length" in mapping_data
        print(f"Chickpea: {seq_name} -> {mapping_data['assigned_molecule']} ({mapping_data['sequence_length']} bp)")


def test_gene_chromosome_mapping():
    """Test that a gene's coordinate sequence can be mapped to a human-readable chromosome."""
    report_path = Path("data/raw/GCF_018294505.1_IWGSC_CS_RefSeq_v2.1_assembly_report.txt")
    
    if not report_path.exists():
        raise FileNotFoundError(f"Test dataset not found: {report_path}")
    
    mappings = load_chromosome_mappings(report_path)
    
    # Get a real sequence name from the mappings
    real_sequence = list(mappings.keys())[0]
    expected_human_label = mappings[real_sequence]["assigned_molecule"]
    
    # Test the mapping function
    result = map_gene_to_human_chromosome(real_sequence, mappings)
    assert result == expected_human_label
    
    # Test fallback for unknown sequence
    unknown_result = map_gene_to_human_chromosome("unknown_sequence", mappings)
    assert unknown_result == "unknown_sequence"  # Should return original if not found
    
    print(f"Successfully mapped {real_sequence} -> {result}")
