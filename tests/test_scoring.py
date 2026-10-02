"""Unit tests for curator/graph/scoring.py -- pure functions over a hand-built bundle, no database."""

from __future__ import annotations

import pytest

from curator.graph.bundle import KGBundle
from curator.graph.scoring import claim_score, conflicted_claim_ids, score_bundle, summarize, tier_for
from curator.model import Claim, Evidence, EvidenceMethod, Source, SourceType, Tier

GENE = "gene:wheat:TestYr1"
DISEASE = "dis:wheat:stripe_rust"
VARIETY = "var:wheat:TESTV1"


def _source(n: int, year: int = 2020) -> Source:
    return Source(id=f"pmid:{n}", type=SourceType.PUBLICATION, title=f"Paper {n}", year=year, verified=True)


def _gene_claim() -> Claim:
    return Claim(type="GENE_CONFERS_RESISTANCE", subject_id=GENE, object_id=DISEASE, qualifiers={"resistance_type": "ASR"})


def _evidence(claim: Claim, source: Source, method=EvidenceMethod.FIELD_MULTI_ENV, **kw) -> Evidence:
    return Evidence(claim_id=claim.id, source_id=source.id, method=method, extractor=kw.pop("extractor", "manual:test"), **kw)


def _reaction(reaction: str, **extra) -> Claim:
    return Claim(
        type="VARIETY_REACTION", subject_id=VARIETY, object_id=DISEASE,
        qualifiers={"reaction": reaction, "stage": "adult", **extra},
    )


def test_single_strong_source_is_tier_a():
    claim, source = _gene_claim(), _source(1)
    score = claim_score(claim, [_evidence(claim, source, EvidenceMethod.CLONED_VALIDATED)], {source.id: source}, as_of_year=2026)
    assert score == 1.0
    assert tier_for(score) is Tier.A


def test_single_review_statement_is_tier_d():
    claim, source = _gene_claim(), _source(1)
    score = claim_score(claim, [_evidence(claim, source, EvidenceMethod.REVIEW_STATEMENT)], {source.id: source}, as_of_year=2026)
    assert score == pytest.approx(0.35)
    assert tier_for(score) is Tier.D


def test_independent_sources_corroborate():
    claim, s1, s2 = _gene_claim(), _source(1), _source(2)
    evidence = [_evidence(claim, s1, EvidenceMethod.FIELD_SINGLE_ENV), _evidence(claim, s2, EvidenceMethod.FIELD_SINGLE_ENV)]
    score = claim_score(claim, evidence, {s1.id: s1, s2.id: s2}, as_of_year=2026)
    assert score == pytest.approx(0.75)  # 1 - 0.5 * 0.5
    assert tier_for(score) is Tier.B


def test_repeated_evidence_from_one_source_counts_once():
    claim, source = _gene_claim(), _source(1)
    evidence = [
        _evidence(claim, source, EvidenceMethod.FIELD_SINGLE_ENV, locator="abstract"),
        _evidence(claim, source, EvidenceMethod.FIELD_MULTI_ENV, locator="results"),
    ]
    score = claim_score(claim, evidence, {source.id: source}, as_of_year=2026)
    assert score == pytest.approx(0.80)  # the strongest row only, not 1 - 0.5 * 0.2


def test_unreviewed_llm_evidence_is_discounted_until_a_human_reviews_it():
    claim, source = _gene_claim(), _source(1)
    quote = "TestYr1 confers all-stage resistance to stripe rust in wheat."
    llm = _evidence(claim, source, EvidenceMethod.FIELD_MULTI_ENV, extractor="llm:m@v1", quote=quote)
    reviewed = _evidence(
        claim, source, EvidenceMethod.FIELD_MULTI_ENV, extractor="llm:m@v1", quote=quote,
        reviewer="vikas", reviewed_at="2026-10-01T00:00:00Z",
    )
    assert claim_score(claim, [llm], {source.id: source}, as_of_year=2026) == pytest.approx(0.48)  # 0.8 * 0.6
    assert claim_score(claim, [reviewed], {source.id: source}, as_of_year=2026) == pytest.approx(0.80)


def test_old_pathotype_dependent_evidence_is_discounted():
    claim = _reaction("R", pathotype_id="path:wheat:TESTPATH")
    old, recent = _source(1, year=2005), _source(2, year=2022)
    ev_old, ev_recent = _evidence(claim, old), _evidence(claim, recent)
    assert claim_score(claim, [ev_old], {old.id: old}, as_of_year=2026) == pytest.approx(0.64)  # 0.8 * 0.8
    assert claim_score(claim, [ev_recent], {recent.id: recent}, as_of_year=2026) == pytest.approx(0.80)


def test_age_does_not_discount_claims_that_are_not_pathotype_dependent():
    claim, old = _gene_claim(), _source(1, year=2005)
    assert claim_score(claim, [_evidence(claim, old)], {old.id: old}, as_of_year=2026) == pytest.approx(0.80)


def test_resistant_vs_susceptible_in_the_same_context_is_a_conflict():
    resistant, susceptible = _reaction("R"), _reaction("S")
    assert conflicted_claim_ids([resistant, susceptible]) == {resistant.id, susceptible.id}


def test_different_places_and_seasons_are_still_a_conflict():
    """Same variety, disease, stage: resistant in one place/year and susceptible in another is exactly the dispute to show
    (competency query CQ10 uses the same definition)."""
    resistant, susceptible = _reaction("R", location="Indore", season="2004"), _reaction("S", location="Delhi", season="2021-22")
    assert conflicted_claim_ids([resistant, susceptible]) == {resistant.id, susceptible.id}


def test_a_report_that_states_no_stage_could_be_about_any_stage():
    stageless = Claim(type="VARIETY_REACTION", subject_id=VARIETY, object_id=DISEASE, qualifiers={"reaction": "R", "stage": "unspecified"})
    susceptible = _reaction("S")
    assert conflicted_claim_ids([stageless, susceptible]) == {stageless.id, susceptible.id}


def test_seedling_susceptible_with_adult_resistant_is_adult_plant_resistance_not_a_conflict():
    seedling = Claim(type="VARIETY_REACTION", subject_id=VARIETY, object_id=DISEASE, qualifiers={"reaction": "S", "stage": "seedling"})
    assert conflicted_claim_ids([seedling, _reaction("R")]) == set()


def test_resistant_to_one_pathotype_and_susceptible_to_another_is_not_a_conflict():
    one, other = _reaction("R", pathotype_id="pt:puccinia_striiformis_f_sp_tritici:A"), _reaction("S", pathotype_id="pt:puccinia_striiformis_f_sp_tritici:B")
    assert conflicted_claim_ids([one, other]) == set()
    assert conflicted_claim_ids([one, _reaction("S")]) == {one.id, _reaction("S").id}  # one side names no pathotype


def test_notification_resistance_to_a_rust_ages_from_the_release_year_not_the_year_of_the_pdf():
    claim = _reaction("R", stage="unspecified")
    pdf = _source(1, year=2021)
    ev = _evidence(claim, pdf, EvidenceMethod.OFFICIAL_DOCUMENT)
    released_2004 = {VARIETY: 2004}
    assert claim_score(claim, [ev], {pdf.id: pdf}, as_of_year=2026, release_years=released_2004) == pytest.approx(0.72)  # 0.9 * 0.8
    assert claim_score(claim, [ev], {pdf.id: pdf}, as_of_year=2026, release_years={VARIETY: 2019}) == pytest.approx(0.90)
    assert claim_score(claim, [ev], {pdf.id: pdf}, as_of_year=2026) == pytest.approx(0.90)  # no release year known: the PDF's year


def test_old_resistance_to_a_disease_without_races_is_not_discounted():
    claim = Claim(type="VARIETY_REACTION", subject_id="var:soybean:TESTS1", object_id="dis:soybean:charcoal_rot", qualifiers={"reaction": "R", "stage": "unspecified"})
    pdf = _source(1, year=2021)
    ev = _evidence(claim, pdf, EvidenceMethod.OFFICIAL_DOCUMENT)
    assert claim_score(claim, [ev], {pdf.id: pdf}, as_of_year=2026, release_years={"var:soybean:TESTS1": 1994}) == pytest.approx(0.90)


def test_intermediate_reactions_do_not_conflict():
    assert conflicted_claim_ids([_reaction("R"), _reaction("I")]) == set()


def test_conflict_caps_the_tier_at_c():
    assert tier_for(0.95, conflict=True) is Tier.C
    assert tier_for(0.70, conflict=True) is Tier.C
    assert tier_for(0.45, conflict=True) is Tier.C
    assert tier_for(0.20, conflict=True) is Tier.D


def test_tier_boundaries():
    assert [tier_for(s) for s in (0.85, 0.849, 0.65, 0.649, 0.40, 0.399)] == [Tier.A, Tier.B, Tier.B, Tier.C, Tier.C, Tier.D]


def test_score_bundle_fills_fields_without_changing_claim_ids_or_inputs():
    claim, s1, s2 = _gene_claim(), _source(1), _source(2)
    bundle = KGBundle(
        sources=[s1, s2], claims=[claim],
        evidence=[_evidence(claim, s1, EvidenceMethod.FIELD_SINGLE_ENV), _evidence(claim, s2, EvidenceMethod.FIELD_SINGLE_ENV)],
    )
    scored = score_bundle(bundle, as_of_year=2026)
    assert scored.claims[0].id == claim.id
    assert (scored.claims[0].score, scored.claims[0].tier, scored.claims[0].conflict) == (0.75, Tier.B, False)
    assert bundle.claims[0].score is None  # the input bundle is untouched


def test_summarize_reports_tier_mix_and_corroboration():
    claim, s1, s2 = _gene_claim(), _source(1), _source(2)
    other = _reaction("R")
    bundle = score_bundle(
        KGBundle(
            sources=[s1, s2], claims=[claim, other],
            evidence=[
                _evidence(claim, s1, EvidenceMethod.FIELD_SINGLE_ENV), _evidence(claim, s2, EvidenceMethod.FIELD_SINGLE_ENV),
                _evidence(other, s1, EvidenceMethod.REVIEW_STATEMENT),
            ],
        ),
        as_of_year=2026,
    )
    summary = summarize(bundle)
    assert summary["tiers"] == {"B": 1, "D": 1}
    assert summary["multi_source_claims"] == 1
    assert summary["single_source_claims"] == 1
