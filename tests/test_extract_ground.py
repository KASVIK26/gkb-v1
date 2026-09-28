"""Unit tests for curator/extract/ground.py and curator/extract/normalize.py."""

from __future__ import annotations

import pytest

from curator.extract.ground import entities_present, ground_candidate, verify_quote
from curator.extract.normalize import RejectedCandidate, build_claim_candidate, resolve_entity_from_bundle
from curator.model.entities import Entity
from curator.model.enums import EntityType
from curator.normalize.synonyms import AmbiguousName

from kg_toy import STRIPE, TRIG, YR1, toy_bundle

SOURCE_TEXT = (
    "TestYr1 confers all-stage resistance to stripe rust in wheat under field conditions. "
    "Infection was assessed across three seasons at two locations."
)


def test_verify_quote_exact_match():
    quote = "TestYr1 confers all-stage resistance to stripe rust in wheat under field conditions."
    assert verify_quote(quote, SOURCE_TEXT)


def test_verify_quote_paraphrase_fails():
    quote = "Stripe rust was completely eliminated in every wheat field that had this gene."
    assert not verify_quote(quote, SOURCE_TEXT)


def test_verify_quote_empty_fails():
    assert not verify_quote("", SOURCE_TEXT)


def test_entities_present_true_when_both_mentioned():
    quote = "TestYr1 confers resistance to stripe rust."
    assert entities_present(quote, ["TestYr1", "stripe rust"])


def test_entities_present_false_when_one_missing():
    quote = "TestYr1 confers resistance to leaf rust."
    assert not entities_present(quote, ["TestYr1", "stripe rust"])


def test_ground_candidate_rejects_short_quote():
    result = ground_candidate(quote="too short", source_text=SOURCE_TEXT, entity_mentions=[])
    assert not result.passed
    assert "characters" in result.reason


def test_ground_candidate_rejects_ungrounded_quote():
    result = ground_candidate(
        quote="This gene was previously reported by another group to be fully durable everywhere.",
        source_text=SOURCE_TEXT,
        entity_mentions=[],
    )
    assert not result.passed
    assert "does not match" in result.reason


def test_ground_candidate_rejects_missing_entity_mention():
    quote = "Infection was assessed across three seasons at two locations."
    result = ground_candidate(quote=quote, source_text=SOURCE_TEXT, entity_mentions=["TestYr1", "stripe rust"])
    assert not result.passed
    assert "does not mention" in result.reason


def test_ground_candidate_passes():
    quote = "TestYr1 confers all-stage resistance to stripe rust in wheat under field conditions."
    result = ground_candidate(quote=quote, source_text=SOURCE_TEXT, entity_mentions=["TestYr1", "stripe rust"])
    assert result.passed
    assert result.reason is None
    assert result.score >= 92


def test_ground_candidate_score_present_even_on_rejection():
    result = ground_candidate(
        quote="This gene was previously reported by another group to be fully durable everywhere.",
        source_text=SOURCE_TEXT,
        entity_mentions=[],
    )
    assert not result.passed
    assert result.score < 92


def test_resolve_entity_from_bundle_finds_gene():
    entities = toy_bundle().entities
    resolved = resolve_entity_from_bundle("TestYr1", EntityType.GENE, entities, "wheat")
    assert resolved == YR1


def test_resolve_entity_from_bundle_returns_none_for_unknown_name():
    entities = toy_bundle().entities
    assert resolve_entity_from_bundle("NoSuchGene", EntityType.GENE, entities, "wheat") is None


def test_resolve_entity_from_bundle_ambiguous_raises():
    entities = [
        Entity(id="gene:wheat:TestDup1", type="Gene", name="DupGene", crop="wheat", props={"symbol": "DupGene"}),
        Entity(id="gene:wheat:TestDup2", type="Gene", name="DupGene", crop="wheat", props={"symbol": "DupGene"}),
    ]
    with pytest.raises(AmbiguousName):
        resolve_entity_from_bundle("DupGene", EntityType.GENE, entities, "wheat")


def test_build_claim_candidate_accepts_gene_confers_resistance():
    entities = toy_bundle().entities
    candidate = {
        "claim_type": "GENE_CONFERS_RESISTANCE",
        "subject": {"type": "Gene", "text": "TestYr1"},
        "object": {"type": "Disease", "text": "stripe rust"},
        "qualifiers": {"resistance_type": "ASR"},
    }
    result = build_claim_candidate(candidate, entities=entities, crop="wheat")

    assert not isinstance(result, RejectedCandidate)
    assert result.subject_id == YR1
    assert result.object_id == STRIPE
    assert result.qualifiers["resistance_type"] == "ASR"


def test_build_claim_candidate_resolves_existing_env_trigger_instead_of_rejecting():
    # A second paper reporting a fact the KG already has an EnvTrigger for should reuse it, not be
    # told it "needs a new entity" every time -- build_claim_candidate tries resolution first.
    entities = toy_bundle().entities
    candidate = {
        "claim_type": "DISEASE_ENV_TRIGGER",
        "subject": {"type": "Disease", "text": "stripe rust"},
        "object": {"type": "EnvTrigger", "text": "TEST stripe rust infection window"},
        "qualifiers": {},
    }
    result = build_claim_candidate(candidate, entities=entities, crop="wheat")

    assert not isinstance(result, RejectedCandidate)
    assert result.subject_id == STRIPE
    assert result.object_id == TRIG


def test_build_claim_candidate_resolves_existing_advisory_instead_of_rejecting():
    entities = toy_bundle().entities + [
        Entity(id="adv:wheat:TESTADV1", type="Advisory", name="TEST fungicide timing advisory",
               crop="wheat", props={"action_type": "chemical"}),
    ]
    candidate = {
        "claim_type": "DISEASE_MANAGED_BY",
        "subject": {"type": "Disease", "text": "stripe rust"},
        "object": {"type": "Advisory", "text": "TEST fungicide timing advisory"},
        "qualifiers": {},
    }
    result = build_claim_candidate(candidate, entities=entities, crop="wheat")

    assert not isinstance(result, RejectedCandidate)
    assert result.subject_id == STRIPE
    assert result.object_id == "adv:wheat:TESTADV1"


def test_build_claim_candidate_rejects_new_entity_object_when_none_match():
    entities = toy_bundle().entities
    candidate = {
        "claim_type": "DISEASE_ENV_TRIGGER",
        "subject": {"type": "Disease", "text": "stripe rust"},
        "object": {"type": "EnvTrigger", "text": "temperature 15-30C with rain"},
        "qualifiers": {},
    }
    result = build_claim_candidate(candidate, entities=entities, crop="wheat")

    assert isinstance(result, RejectedCandidate)
    assert "EnvTrigger entity" in result.reason


def test_build_claim_candidate_rejects_unknown_claim_type():
    result = build_claim_candidate(
        {"claim_type": "NOT_A_REAL_TYPE", "subject": {}, "object": {}}, entities=[], crop="wheat"
    )
    assert isinstance(result, RejectedCandidate)
    assert "unknown claim_type" in result.reason


def test_build_claim_candidate_rejects_unresolvable_subject():
    entities = toy_bundle().entities
    candidate = {
        "claim_type": "GENE_CONFERS_RESISTANCE",
        "subject": {"type": "Gene", "text": "SomeGeneNotInTheBundle"},
        "object": {"type": "Disease", "text": "stripe rust"},
        "qualifiers": {},
    }
    result = build_claim_candidate(candidate, entities=entities, crop="wheat")
    assert isinstance(result, RejectedCandidate)
    assert "subject" in result.reason
