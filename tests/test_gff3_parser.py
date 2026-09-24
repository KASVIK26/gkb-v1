"""Tests for GFF3 parsing.

Uses a 5-line excerpt of the real IWGSC CS RefSeq v2.1 GFF (tests/fixtures/) so the
suite runs in CI without the 800 MB source file.
"""

import gzip
import shutil
from pathlib import Path

import pytest

from curator.parsers.gff_parser import parse_gff3, extract_resistance_genes
from curator.parsers.genomic_integration import load_chromosome_mappings

FIXTURES = Path(__file__).parent / "fixtures"
MINI_GFF = FIXTURES / "mini_wheat.gff3"
MINI_REPORT = FIXTURES / "mini_wheat_assembly_report.txt"


def test_parse_gff3_extracts_only_gene_features():
    genes = parse_gff3(MINI_GFF)

    # region and mRNA lines are skipped; the two gene lines are kept
    assert [g["id"] for g in genes] == ["gene-LOC123073777", "gene-LOC123185447"]
    rpm1 = genes[1]
    assert rpm1["name"] == "LOC123185447"
    assert (rpm1["start"], rpm1["end"], rpm1["strand"]) == (9963900, 9971358, "-")
    assert rpm1["length"] == 9971358 - 9963900 + 1


def test_parse_gff3_without_mapping_keeps_sequence_id():
    genes = parse_gff3(MINI_GFF)
    assert all(g["chromosome"] == "NC_057794.1" for g in genes)


def test_parse_gff3_with_chromosome_mapping():
    mappings = load_chromosome_mappings(MINI_REPORT)
    genes = parse_gff3(MINI_GFF, mappings)

    assert all(g["seqname"] == "NC_057794.1" for g in genes)
    assert all(g["chromosome"] == "1A" for g in genes)


def test_gff3_parsing_handles_gzip(tmp_path):
    gz_path = tmp_path / "mini_wheat.gff3.gz"
    with MINI_GFF.open("rb") as src, gzip.open(gz_path, "wb") as dst:
        shutil.copyfileobj(src, dst)

    assert parse_gff3(gz_path) == parse_gff3(MINI_GFF)


def test_parse_gff3_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        parse_gff3(tmp_path / "missing.gff3")


def test_extract_resistance_genes_matches_keywords():
    genes = parse_gff3(MINI_GFF)
    hits = extract_resistance_genes(genes, resistance_keywords=["LOC123185447"])
    assert [g["id"] for g in hits] == ["gene-LOC123185447"]
