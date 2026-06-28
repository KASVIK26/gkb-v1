"""Tests for assembly report parsing and chromosome mapping."""

from pathlib import Path

from curator.parsers.assembly_parser import parse_assembly_report


def test_parse_wheat_assembly_report():
    """Test parsing the wheat IWGSC assembly report."""
    report_path = Path("data/raw/GCF_018294505.1_IWGSC_CS_RefSeq_v2.1_assembly_report.txt")
    
    if not report_path.exists():
        raise FileNotFoundError(f"Test dataset not found: {report_path}")
    
    metadata, mappings = parse_assembly_report(report_path)
    
    # Verify header metadata
    assert metadata.organism_name == "Triticum aestivum (bread wheat)"
    assert metadata.cultivar == "Chinese Spring"
    assert metadata.taxid == 4565
    
    # Verify that chromosome mappings were extracted
    assert len(mappings) > 0
    
    # Wheat should have mappings for chromosomes 1A, 1B, 1D, etc.
    sequence_names = [m.sequence_name for m in mappings]
    assert any("chr" in name.lower() for name in sequence_names), f"Expected chromosome IDs in {sequence_names}"


def test_parse_chickpea_assembly_report():
    """Test parsing the chickpea assembly report."""
    report_path = Path("data/raw/GCA_000347275.4_ASM34727v4_assembly_report.txt")
    
    if not report_path.exists():
        raise FileNotFoundError(f"Test dataset not found: {report_path}")
    
    metadata, mappings = parse_assembly_report(report_path)
    
    # Verify header metadata
    assert metadata.organism_name == "Cicer arietinum (chickpea)"
    assert metadata.cultivar == "ICC4958"
    assert metadata.taxid == 3827
    
    # Verify that chromosome mappings were extracted
    assert len(mappings) > 0
    
    # Chickpea should have mappings for Ca1, Ca2, etc. (or Ca_LG1, etc. as sequence names)
    assigned_molecules = {m.assigned_molecule for m in mappings if m.sequence_role == "assembled-molecule"}
    assert len(assigned_molecules) > 0, f"Expected assigned molecules in mappings"


def test_chromosome_mapping_lookup():
    """Test that chromosome mappings can be used for gene coordinate translation."""
    report_path = Path("data/raw/GCF_018294505.1_IWGSC_CS_RefSeq_v2.1_assembly_report.txt")
    
    if not report_path.exists():
        raise FileNotFoundError(f"Test dataset not found: {report_path}")
    
    metadata, mappings = parse_assembly_report(report_path)
    
    # Create a lookup dict: sequence_name -> ChromosomeMapping
    mapping_dict = {m.sequence_name: m for m in mappings}
    
    # If we have a gene on sequence "NC_...", we can look it up
    if mapping_dict:
        first_mapping = list(mapping_dict.values())[0]
        assert first_mapping.sequence_length > 0
        assert first_mapping.assigned_molecule
        print(f"Mapped {first_mapping.sequence_name} -> {first_mapping.assigned_molecule} ({first_mapping.sequence_length} bp)")
