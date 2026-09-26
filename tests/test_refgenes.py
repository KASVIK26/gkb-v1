"""Tests for curator/genome/refgenes.py (RESEARCH_ROADMAP.md Phase 4 tasks 4.1-4.2).

Fixtures are small excerpts of the real chickpea/soybean/wheat GFF3 files in data/raw/ (real gene
lines, real Dbxref domain annotations -- not synthesised), so the classifier is exercised against
genuine InterPro accession combinations rather than made-up ones.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from curator.genome.refgenes import parse_ncbi_assembly_report, stream_ref_genes

FIXTURES = Path(__file__).parent / "fixtures"


def test_chickpea_tnl_gene_is_classified_correctly():
    """Ca_01332 carries NB-ARC (IPR002182) + TIR (IPR000157) -- a textbook TNL."""
    genes = {g.locus_id: g for g in stream_ref_genes(FIXTURES / "mini_chickpea.gff3", crop="chickpea", assembly="ICC4958.gnm2")}
    gene = genes["cicar.ICC4958.gnm2.ann1.Ca_01332"]
    assert gene.is_nlr is True
    assert gene.nlr_class == "TNL"
    assert gene.chromosome == "cicar.ICC4958.gnm2.Ca1"  # no chromosome_map given -- keeps seqname
    assert (gene.start_bp, gene.end_bp, gene.strand) == (18542839, 18547304, "-")


def test_chickpea_nb_arc_without_tir_is_nl_not_tnl():
    """Ca_00037's own Note text says 'TIR-NBS-LRR class', but its actual Dbxref domain list has
    NB-ARC (IPR002182) with no TIR (IPR000157) -- the domain-based call (NL) must not be swayed by
    the free-text annotation. This is exactly why a domain-ID classifier was used instead of a
    keyword match on Note/description."""
    genes = {g.locus_id: g for g in stream_ref_genes(FIXTURES / "mini_chickpea.gff3", crop="chickpea", assembly="ICC4958.gnm2")}
    gene = genes["cicar.ICC4958.gnm2.ann1.Ca_00037"]
    assert gene.is_nlr is True
    assert gene.nlr_class == "NL"


def test_non_nlr_gene_is_not_flagged():
    genes = {g.locus_id: g for g in stream_ref_genes(FIXTURES / "mini_chickpea.gff3", crop="chickpea", assembly="ICC4958.gnm2")}
    gene = genes["cicar.ICC4958.gnm2.ann1.Ca_00001"]  # NEDD8-activating enzyme -- not NLR-related
    assert gene.is_nlr is False
    assert gene.nlr_class is None


def test_soybean_kinase_plus_lrr_is_rlk():
    genes = {g.locus_id: g for g in stream_ref_genes(FIXTURES / "mini_soybean.gff3", crop="soybean", assembly="Wm82.gnm6")}
    gene = genes["glyma.Wm82.gnm6.ann1.Glyma.01G007400"]
    assert gene.is_nlr is True
    assert gene.nlr_class == "RLK"


def test_soybean_non_domain_gene_is_not_flagged():
    genes = {g.locus_id: g for g in stream_ref_genes(FIXTURES / "mini_soybean.gff3", crop="soybean", assembly="Wm82.gnm6")}
    gene = genes["glyma.Wm82.gnm6.ann1.Glyma.01G000100"]
    assert gene.is_nlr is False


def test_classify_domains_false_disables_classification():
    genes = list(
        stream_ref_genes(FIXTURES / "mini_chickpea.gff3", crop="chickpea", assembly="ICC4958.gnm2", classify_domains=False)
    )
    assert all(g.is_nlr is False and g.nlr_class is None for g in genes)
    # Domains are still recorded even when classification is skipped.
    assert any(g.domains for g in genes)


def test_wheat_has_no_domain_data_so_is_never_flagged():
    """The wheat GFF (NCBI RefSeq) carries no InterPro Dbxrefs at all -- even a gene whose free-text
    description literally says 'disease resistance protein' must come back is_nlr=False, since
    there is no real domain evidence to base a claim on. Keyword-matching Note/description text
    instead would produce exactly the kind of ungrounded claim this project exists to avoid."""
    genes = {g.locus_id: g for g in stream_ref_genes(FIXTURES / "mini_wheat.gff3", crop="wheat", assembly="IWGSC_CS_RefSeq_v2.1")}
    rpm1 = genes["gene-LOC123185447"]
    assert "disease resistance protein RPM1" in (rpm1.description or "")
    assert rpm1.is_nlr is False
    assert rpm1.nlr_class is None
    # Dbxref carries a GeneID cross-ref but no InterPro: entries at all in this file.
    assert not any(d.startswith("InterPro:") for d in rpm1.domains)


def test_chromosome_map_translates_wheat_seqnames():
    mapping = parse_ncbi_assembly_report(FIXTURES / "mini_wheat_assembly_report.txt")
    genes = list(stream_ref_genes(FIXTURES / "mini_wheat.gff3", crop="wheat", assembly="IWGSC_CS_RefSeq_v2.1", chromosome_map=mapping))
    assert all(g.chromosome == "1A" for g in genes)


def test_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        list(stream_ref_genes(FIXTURES / "does_not_exist.gff3", crop="wheat", assembly="x"))


def test_stream_ref_genes_is_a_real_generator_not_a_list():
    """Task 4.1 explicitly asks for a streaming generator (memory-bounded for an 800MB+ file),
    not a function that loads everything into a list before returning."""
    import types

    result = stream_ref_genes(FIXTURES / "mini_wheat.gff3", crop="wheat", assembly="x")
    assert isinstance(result, types.GeneratorType)
