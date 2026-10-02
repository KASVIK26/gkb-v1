"""Tests for the kg/ file loader, the vocab-derived reference entities, and the real
production content in kg/curated/ (no database needed for any of this)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from curator.graph.bundle import KGBundle
from curator.graph.kg_files import load_curated_dir, load_curated_file
from curator.graph.variety_import import variety_bundle
from curator.graph.vocab_entities import reference_bundle
from curator.model import ClaimType, EntityType

ROOT_DIR = Path(__file__).resolve().parents[1]
KG_CURATED_DIR = ROOT_DIR / "kg" / "curated"


def _production_bundle() -> KGBundle:
    # same composition as curator.cli._build_bundle: curated claims may name notified varieties
    return KGBundle.merge(reference_bundle(), variety_bundle(), load_curated_dir(KG_CURATED_DIR))


# ─────────────────────────── reference_bundle() ───────────────────────────
def test_reference_bundle_covers_all_17_diseases():
    bundle = reference_bundle()
    diseases = [e for e in bundle.entities if e.type is EntityType.DISEASE]
    assert len(diseases) == 17
    assert {e.crop for e in diseases} == {"wheat", "soybean", "chickpea"}


def test_reference_bundle_shares_one_pathogen_across_crops():
    bundle = reference_bundle()
    pathogens = {e.id for e in bundle.entities if e.type is EntityType.PATHOGEN}
    macrophomina = "path:macrophomina_phaseolina"
    assert macrophomina in pathogens
    # docs/scope.md: soybean charcoal rot and chickpea dry root rot share this pathogen —
    # it must be ONE entity, not two, or the cross-crop link the roadmap highlights is lost.
    causes = [c for c in bundle.claims if c.type is ClaimType.DISEASE_CAUSED_BY and c.object_id == macrophomina]
    assert {c.subject_id for c in causes} == {"dis:soybean:charcoal_rot", "dis:chickpea:dry_root_rot"}


def test_reference_bundle_passes_its_own_gates():
    bundle = reference_bundle()
    assert bundle.gate_errors() == []


def test_reference_bundle_wires_pathogen_synonyms():
    # config/vocab/diseases.yaml's `pathogen_synonyms` field used to be silently ignored --
    # the Pathogen Entity was built with no `synonyms=` at all, so even a paper's own common
    # abbreviated form (e.g. "C. sojina" for Cercospora sojina) could never resolve. Caught via
    # eval/run_eval.py's live pilot (PHASES.md item 29).
    bundle = reference_bundle()
    cercospora = next(e for e in bundle.entities if e.id == "path:cercospora_sojina")
    assert "C. sojina" in cercospora.synonyms


# ─────────────────────────── load_curated_file() ───────────────────────────
def test_load_curated_file_parses_claim_and_nested_evidence(tmp_path):
    doc = {
        "sources": [{"id": "pmid:1", "type": "publication", "title": "t", "verified": True}],
        "entities": [
            {"id": "gene:wheat:TestG1", "type": "Gene", "name": "TestG1", "crop": "wheat",
             "props": {"symbol": "TestG1", "chromosome": "2B"}},
            {"id": "dis:wheat:stem_rust", "type": "Disease", "name": "Stem rust", "crop": "wheat"},
        ],
        "claims": [
            {
                "type": "GENE_CONFERS_RESISTANCE",
                "subject": "gene:wheat:TestG1",
                "object": "dis:wheat:stem_rust",
                "qualifiers": {"resistance_type": "ASR"},
                "evidence": [{"source": "pmid:1", "method": "cloned_validated", "locator": "abstract"}],
            }
        ],
    }
    path = tmp_path / "test.yaml"
    path.write_text(yaml.dump(doc), encoding="utf-8")

    bundle = load_curated_file(path)
    assert len(bundle.entities) == 2 and len(bundle.sources) == 1
    assert len(bundle.claims) == 1 and len(bundle.evidence) == 1
    assert bundle.evidence[0].claim_id == bundle.claims[0].id


def test_load_curated_file_rejects_claim_without_evidence(tmp_path):
    doc = {
        "entities": [{"id": "gene:wheat:X", "type": "Gene", "name": "X", "crop": "wheat", "props": {"symbol": "X"}}],
        "claims": [{"type": "VARIETY_CARRIES_GENE", "subject": "var:wheat:Y", "object": "gene:wheat:X"}],
    }
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.dump(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="no evidence"):
        load_curated_file(path)


def test_load_curated_dir_missing_returns_empty_bundle(tmp_path):
    bundle = load_curated_dir(tmp_path / "does_not_exist")
    assert bundle == KGBundle()


# ─────────────────────────── the real production content ───────────────────────────
def test_production_kg_files_pass_release_gates():
    """Guards kg/curated/*.yaml itself: a future bad edit fails CI here, not in Supabase."""
    bundle = _production_bundle()
    assert bundle.gate_errors() == []


def test_production_wheat_genes_have_correct_chromosomes():
    """Regression test for the Sr33 chromosome error made and then fixed during this project
    (RESEARCH_ROADMAP.md §2.2 D3): 1B (original seed) -> 1DL (first "fix") -> 1DS (verified)."""
    bundle = _production_bundle()
    by_id = {e.id: e for e in bundle.entities}
    expected_chromosomes = {
        "gene:wheat:Sr33": "1DS", "gene:wheat:Sr35": "3AL", "gene:wheat:Lr34": "7DS",
        "gene:wheat:Sr2": "3BS", "gene:wheat:Sr50": "1D",
        # The classic 1BL.1RS rye translocation cluster: three separate genes, same chromosome arm.
        "gene:wheat:Sr31": "1BL", "gene:wheat:Lr26": "1BL", "gene:wheat:Yr9": "1BL",
        "gene:wheat:Fhb1": "3BS", "gene:wheat:Lr21": "1DS",
    }
    for gene_id, chromosome in expected_chromosomes.items():
        assert by_id[gene_id].props["chromosome"] == chromosome, gene_id
    assert set(by_id["gene:wheat:Lr34"].synonyms) == {"Yr18", "Sr57", "Pm38"}
    # Sr2/Lr27 is a "multiple resistance locus" per its own source, not a proven single cloned
    # gene like Lr34 -- must NOT be collapsed into a synonym relationship without a cloning paper.
    assert by_id["gene:wheat:Sr2"].synonyms == []


def test_production_tracks_a_defeated_gene():
    """Sr31, defeated by Ug99 in Uganda, 1999 -- the discovery that triggered global Ug99
    surveillance. A concrete instance of RESEARCH_ROADMAP.md Phase 12's gene-effectiveness-
    over-time analysis."""
    bundle = _production_bundle()
    defeated = [
        c for c in bundle.claims
        if c.type is ClaimType.GENE_PATHOTYPE_INTERACTION and c.qualifiers.get("outcome") == "defeated"
    ]
    dated = [(c.subject_id, c.object_id, c.qualifiers["year"]) for c in defeated if "year" in c.qualifiers]
    assert dated == [("gene:wheat:Sr31", "pt:puccinia_graminis_f_sp_tritici:Ug99", 1999)]
    # IIWBR Mehtaensis 2026 (work order WO07): the new brown-rust pathotype 52-6 defeats Lr24 and Lr39, undated in the source
    assert {(c.subject_id, c.object_id) for c in defeated if "year" not in c.qualifiers} == {
        ("gene:wheat:Lr24", "pt:puccinia_triticina:52-6"), ("gene:wheat:Lr39", "pt:puccinia_triticina:52-6")}


def test_production_claims_only_cite_verified_publications():
    bundle = _production_bundle()
    sources = {s.id: s for s in bundle.sources}
    for ev in bundle.evidence:
        source = sources[ev.source_id]
        if source.type.value == "publication":
            assert source.verified, f"{source.id} is cited but not marked verified"


def test_charcoal_rot_gwas_loci_come_from_the_papers_tables():
    """pmid:41477268 Tables 6-8: 18 SNP loci (8 glasshouse/seedling, 10 sick-plot/adult), positions in Wm82.a2.v1, and the defence genes near them."""
    bundle = _production_bundle()
    qtl = {c.subject_id: c for c in bundle.claims if c.type is ClaimType.QTL_ASSOCIATION and c.object_id == "dis:soybean:charcoal_rot"}
    assert len(qtl) == 18
    peak = qtl["qtl:soybean:S14_51754926"].qualifiers
    assert (peak["stage"], peak["assembly"], peak["start_bp"], peak["p_value"]) == ("adult", "Wm82.a2.v1", 47666485, 1.33e-09)
    assert qtl["qtl:soybean:S14_50857981"].qualifiers["stage"] == "seedling"
    contains = [c for c in bundle.claims if c.type is ClaimType.QTL_CONTAINS_REFGENE and c.subject_id.startswith("qtl:soybean:")]
    assert len(contains) >= 20
    assert {e.id for e in bundle.entities if e.id.startswith("ref:soybean:Glyma.14G2045")} == {"ref:soybean:Glyma.14G204500"}
