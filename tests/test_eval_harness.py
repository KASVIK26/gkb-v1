"""Tests for eval/run_eval.py -- fully synthetic, no live network/LLM (mirrors
tests/test_lit_run_extraction.py's convention of hand-built Claim/Evidence/AcceptedCandidate
objects rather than a real paper). Proves the matching/metric logic is correct before it's ever
pointed at a real gold file.
"""

from __future__ import annotations

from curator.extract.normalize import RejectedCandidate
from curator.lit.run_extraction import AcceptedCandidate, ExtractionResult
from curator.model.claims import Claim, Evidence, Source
from curator.model.enums import EvidenceMethod
from eval.run_eval import score_extraction
from eval.schema import GoldClaim

YR1 = "gene:wheat:TestYr1"
STRIPE = "dis:wheat:stripe_rust"
V1 = "var:wheat:TESTV1"

_SOURCE = Source(id="pmid:1", type="publication", title="Test paper", verified=True)


def _accepted(claim: Claim) -> AcceptedCandidate:
    evidence = Evidence(
        claim_id=claim.id, source_id=_SOURCE.id, method=EvidenceMethod.REVIEW_STATEMENT,
        extractor="llm:test-model@claim_extraction_v1",
        quote="A verbatim test quote of at least twenty characters.",
    )
    return AcceptedCandidate(claim=claim, evidence=evidence, grounding_score=97.0)


def _gold_gcr(*, resistance_type: str = "ASR", subject_id: str | None = YR1, object_id: str | None = STRIPE) -> GoldClaim:
    return GoldClaim(
        source_id="pmid:1", claim_type="GENE_CONFERS_RESISTANCE", subject_text="TestYr1", subject_id=subject_id,
        object_text="stripe rust", object_id=object_id, qualifiers={"resistance_type": resistance_type},
        quote="TestYr1 confers all-stage resistance to stripe rust.", section="abstract", annotator="test",
    )


def test_exact_match_counts_as_strict_and_relaxed_tp():
    gold = [_gold_gcr()]
    claim = Claim(type="GENE_CONFERS_RESISTANCE", subject_id=YR1, object_id=STRIPE, qualifiers={"resistance_type": "ASR"})
    result = ExtractionResult(source=_SOURCE, accepted=[_accepted(claim)])

    report = score_extraction(gold, result)

    assert (report.strict_tp, report.strict_fp, report.strict_fn) == (1, 0, 0)
    assert (report.relaxed_tp, report.relaxed_fp, report.relaxed_fn) == (1, 0, 0)


def test_qualifier_mismatch_is_strict_miss_but_relaxed_tp():
    gold = [_gold_gcr(resistance_type="ASR")]
    claim = Claim(type="GENE_CONFERS_RESISTANCE", subject_id=YR1, object_id=STRIPE, qualifiers={"resistance_type": "APR"})
    result = ExtractionResult(source=_SOURCE, accepted=[_accepted(claim)])

    report = score_extraction(gold, result)

    assert (report.strict_tp, report.strict_fp, report.strict_fn) == (0, 1, 1)
    assert (report.relaxed_tp, report.relaxed_fp, report.relaxed_fn) == (1, 0, 0)


def test_missing_prediction_counts_as_false_negative():
    gold = [_gold_gcr()]
    result = ExtractionResult(source=_SOURCE, accepted=[])

    report = score_extraction(gold, result)

    assert report.strict_fn == 1
    assert report.relaxed_fn == 1
    assert report.strict_tp == 0


def test_extra_prediction_counts_as_hallucination_candidate():
    claim = Claim(type="GENE_CONFERS_RESISTANCE", subject_id=YR1, object_id=STRIPE, qualifiers={"resistance_type": "ASR"})
    result = ExtractionResult(source=_SOURCE, accepted=[_accepted(claim)])

    report = score_extraction([], result)

    assert report.extra_predicted == 1
    assert report.relaxed_fp == 1


def test_gold_unresolvable_excluded_from_precision_recall():
    unresolvable = GoldClaim(
        source_id="pmid:1", claim_type="VARIETY_CARRIES_GENE", subject_text="Some New Variety", subject_id=None,
        object_text="TestYr1", object_id=YR1, qualifiers={"method": "marker"},
        quote="Some New Variety carries TestYr1 based on marker screening data here.",
        section="abstract", annotator="test",
    )
    resolvable = _gold_gcr()
    claim = Claim(type="GENE_CONFERS_RESISTANCE", subject_id=YR1, object_id=STRIPE, qualifiers={"resistance_type": "ASR"})
    result = ExtractionResult(source=_SOURCE, accepted=[_accepted(claim)])

    report = score_extraction([unresolvable, resolvable], result)

    assert len(report.gold_unresolvable) == 1
    assert report.gold_unresolvable[0].subject_text == "Some New Variety"
    assert report.strict_tp == 1
    assert report.strict_fn == 0  # the unresolvable gold claim must not be counted as a miss


def test_gold_needs_human_entity_excluded_from_precision_recall():
    trigger_claim = GoldClaim(
        source_id="pmid:1", claim_type="DISEASE_ENV_TRIGGER", subject_text="stripe rust", subject_id=STRIPE,
        object_text="temperature 7-15C with leaf wetness", object_id=None, qualifiers={},
        quote="Infection required temperatures of 7-15C combined with leaf wetness.",
        section="abstract", annotator="test",
    )
    result = ExtractionResult(source=_SOURCE, accepted=[], rejected=[])

    report = score_extraction([trigger_claim], result)

    assert len(report.gold_needs_human_entity) == 1
    assert report.strict_fn == 0
    assert report.relaxed_fn == 0


def test_rejected_reasons_and_grounding_scores_are_reported():
    claim = Claim(type="GENE_CONFERS_RESISTANCE", subject_id=YR1, object_id=STRIPE, qualifiers={"resistance_type": "ASR"})
    result = ExtractionResult(
        source=_SOURCE,
        accepted=[_accepted(claim)],
        rejected=[RejectedCandidate(reason="could not resolve subject 'Unknown Gene'", raw={})],
    )

    report = score_extraction([], result)

    assert report.rejected_reasons["could not resolve subject 'Unknown Gene'"] == 1
    assert report.grounding_scores == [97.0]


def test_render_produces_nonempty_markdown():
    gold = [_gold_gcr()]
    claim = Claim(type="GENE_CONFERS_RESISTANCE", subject_id=YR1, object_id=STRIPE, qualifiers={"resistance_type": "ASR"})
    result = ExtractionResult(source=_SOURCE, accepted=[_accepted(claim)])

    report = score_extraction(gold, result)
    text = report.render()

    assert isinstance(text, str) and text
    assert "Precision" in text
    assert "Recall" in text
