"""Tests for curator/genome/wheat_domains.py -- the NCBI<->IWGSC coordinate-overlap join that
gives wheat's ref_gene rows real InterPro-based NLR/RLK classification.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from curator.genome.wheat_domains import (
    load_iwgsc_gene_intervals,
    load_iwgsc_interpro_domains,
    overlap_join,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_iwgsc_gene_intervals_strips_chr_prefix_and_sorts():
    df = load_iwgsc_gene_intervals(FIXTURES / "mini_iwgsc_HC.gff3")
    assert list(df["chromosome"].unique()) == ["1A"]
    assert list(df["traescs_id"]) == [
        "TraesCS1A03G0004000", "TraesCS1A03G0021300", "TraesCS1A03G0040000", "TraesCS1A03G0040100",
    ]
    assert df["start_bp"].is_monotonic_increasing


def test_load_iwgsc_interpro_domains_only_keeps_interpro_rows():
    domains = load_iwgsc_interpro_domains(FIXTURES / "mini_iwgsc_functional_annotation.csv")
    # TraesCS1A03G0004000 has one Pfam row and one InterPro row -- only the InterPro one counts.
    assert domains["TraesCS1A03G0004000"] == {"IPR001383"}
    assert domains["TraesCS1A03G0021300"] == {"IPR002182", "IPR000157"}


def test_overlap_join_matches_unambiguous_single_overlap():
    ncbi = pd.DataFrame([
        {"locus_id": "gene-LOC-ribosomal", "chromosome": "1A", "start_bp": 1142839, "end_bp": 1144428},
        {"locus_id": "gene-LOC-rpm1", "chromosome": "1A", "start_bp": 9963900, "end_bp": 9971358},
    ])
    iwgsc = load_iwgsc_gene_intervals(FIXTURES / "mini_iwgsc_HC.gff3")
    result = overlap_join(ncbi, iwgsc)
    assert result == {
        "gene-LOC-ribosomal": "TraesCS1A03G0004000",
        "gene-LOC-rpm1": "TraesCS1A03G0021300",
    }


def test_overlap_join_excludes_ambiguous_multi_overlap():
    """An NCBI gene spanning both TraesCS1A03G0040000 (20000000-20001000) and
    TraesCS1A03G0040100 (20000500-20002000) must NOT be resolved to either -- picking one would be
    a guess, not a grounded transfer."""
    ncbi = pd.DataFrame([
        {"locus_id": "gene-LOC-ambiguous", "chromosome": "1A", "start_bp": 19999900, "end_bp": 20002100},
    ])
    iwgsc = load_iwgsc_gene_intervals(FIXTURES / "mini_iwgsc_HC.gff3")
    result = overlap_join(ncbi, iwgsc)
    assert "gene-LOC-ambiguous" not in result


def test_overlap_join_excludes_no_overlap():
    ncbi = pd.DataFrame([
        {"locus_id": "gene-LOC-nowhere", "chromosome": "1A", "start_bp": 500000000, "end_bp": 500000100},
    ])
    iwgsc = load_iwgsc_gene_intervals(FIXTURES / "mini_iwgsc_HC.gff3")
    assert overlap_join(ncbi, iwgsc) == {}


def test_overlap_join_handles_chromosomes_absent_from_either_side():
    ncbi = pd.DataFrame([{"locus_id": "x", "chromosome": "7D", "start_bp": 1, "end_bp": 100}])
    iwgsc = load_iwgsc_gene_intervals(FIXTURES / "mini_iwgsc_HC.gff3")  # only has chromosome 1A
    assert overlap_join(ncbi, iwgsc) == {}
