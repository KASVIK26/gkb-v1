"""curator/graph/qc.py -- the QC report and the sensitivity analysis, on the production graph (no database)."""

from __future__ import annotations

from curator.graph import scoring
from curator.graph.qc import SCENARIOS, qc_report, sensitivity, to_markdown
from curator.model.enums import EVIDENCE_WEIGHT
from tests.test_kg_files import _production_bundle


def _scored():
    return scoring.score_bundle(_production_bundle())


def test_the_production_graph_has_no_provenance_holes():
    report = qc_report(_scored())
    p = report["provenance"]
    assert p["without_evidence"] == 0 and p["evidence_citing_a_missing_source"] == 0 and p["evidence_citing_an_unverified_source"] == 0
    assert report["confidence"]["tiers"] and sum(report["confidence"]["tiers"].values()) == p["claims"]
    # every in-scope disease appears in the coverage table, with the gaps spelled out
    assert len(report["disease_coverage"]) == 17 and report["disease_gaps"]


def test_sensitivity_baseline_matches_the_graph_and_leaves_the_constants_alone():
    bundle = _production_bundle()
    before = (scoring.LLM_UNREVIEWED_FACTOR, scoring.STALE_PATHOTYPE_FACTOR, scoring.TIER_THRESHOLDS, dict(EVIDENCE_WEIGHT))
    sens = sensitivity(bundle)
    after = (scoring.LLM_UNREVIEWED_FACTOR, scoring.STALE_PATHOTYPE_FACTOR, scoring.TIER_THRESHOLDS, dict(EVIDENCE_WEIGHT))
    assert before == after                                              # every scenario is restored, whatever happened
    scored = scoring.score_bundle(bundle)
    assert sens["baseline"] == qc_report(scored)["confidence"]["tiers"]
    assert len(sens["scenarios"]) == len(SCENARIOS)
    harsher = next(s for s in sens["scenarios"] if s["scenario"].startswith("model-evidence discount 0.4"))
    milder = next(s for s in sens["scenarios"] if s["scenario"].startswith("no model-evidence discount"))
    assert harsher["moving_up"] == 0 and milder["moving_down"] == 0     # the direction of each change is the expected one


def test_the_markdown_report_renders_every_section():
    scored = _scored()
    text = to_markdown(qc_report(scored), sensitivity(_production_bundle()), release="test")
    for heading in ("## Scale", "## Provenance", "## Confidence", "## Coverage", "## Structure", "## Against the roadmap targets", "## Sensitivity"):
        assert heading in text


def test_analytics_tables_are_consistent_with_the_claims():
    from curator.graph.analytics import analytics, to_markdown as analytics_markdown

    a = analytics(_scored())
    assert a["multi_rust_donors"] and all(set(r["tiers"]) == {"stem rust", "leaf rust", "stripe rust"} for r in a["multi_rust_donors"])
    assert all(0 <= r["legacy_translocation_share"] <= 1 and 0 < r["concentration_hhi"] <= 1 for r in a["gene_deployment"])
    assert all(0 <= r["susceptible_share"] <= 1 and r["readings"] >= 3 for r in a["susceptibility_index"]["most_susceptible"])
    assert any(r["state"] == "MP" and r["dominant_pathotype"] == "Pgt 11" for r in a["dominant_pathotypes"])     # the central-India stem-rust survey rows are in
    assert "## Wheat varieties resistant" in analytics_markdown(a)
