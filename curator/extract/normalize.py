"""Map an LLM candidate's free-text subject/object mentions to canonical entity IDs.

Reuses curator.model.enums.CLAIM_SIGNATURE (the single source of truth for which entity types a
claim type connects) so this module can never silently accept a claim/entity-type pairing that
`Claim`'s own validator would reject later anyway.

Never guesses: an ambiguous name (curator.normalize.synonyms.AmbiguousName) or an unresolvable one
is surfaced as a RejectedCandidate with a reason, exactly like the rest of this project's curation
discipline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from curator.model.claims import Claim, Evidence
from curator.model.enums import CLAIM_SIGNATURE, ClaimType, Crop, EntityType, EvidenceMethod
from curator.normalize.ids import parse_id
from curator.normalize.synonyms import AmbiguousName, SynonymIndex

# Object types that name a brand-new, per-fact entity (an EnvTrigger's numeric conditions, an
# Advisory's practice) rather than something already in the vocabulary. These can never be
# resolved by synonym lookup -- they don't exist yet. Building them (props, sensor-variable
# mapping, bbch range) is deliberately left to a human curator for this pass of Phase 5;
# see curator/llm/prompts/claim_extraction_v1.md's own note on this.
NEW_ENTITY_TYPES = frozenset({EntityType.ENV_TRIGGER, EntityType.ADVISORY})

SUPPORTED_CLAIM_TYPES = frozenset({
    ClaimType.GENE_CONFERS_RESISTANCE,
    ClaimType.VARIETY_CARRIES_GENE,
    ClaimType.VARIETY_REACTION,
    ClaimType.DISEASE_CAUSED_BY,
    ClaimType.DISEASE_ENV_TRIGGER,
    ClaimType.DISEASE_MANAGED_BY,
})


@dataclass(frozen=True)
class RejectedCandidate:
    reason: str
    raw: dict[str, Any]


def resolve_disease(text: str, crop: Crop | str) -> str | None:
    """Resolve free text to a canonical dis:<crop>:<slug> ID via the disease vocabulary."""
    return SynonymIndex.from_disease_vocab().resolve(text, crop)


def resolve_entity_from_bundle(
    text: str,
    entity_type: EntityType,
    entities: list,
    crop: Crop | str | None = None,
) -> str | None:
    """Resolve free text to a canonical entity ID by indexing an already-loaded KGBundle's entities.

    Genes/varieties have no dedicated vocab file (unlike diseases), so the index is built on the
    fly from whatever entities are already known (each Entity already carries `.name` and
    `.synonyms` -- no new vocab file needed). Raises AmbiguousName rather than guessing.
    """
    index = SynonymIndex()
    for entity in entities:
        if entity.type != entity_type:
            continue
        index.add(entity.id, entity.name, *entity.synonyms)
    return index.resolve(text, crop)


def build_claim_candidate(
    candidate: dict[str, Any],
    *,
    entities: list,
    crop: Crop | str,
) -> Claim | RejectedCandidate:
    """Turn one grounded LLM candidate dict into a real Claim, or a rejection with a reason.

    Assumes `candidate` has already passed curator.extract.ground.ground_candidate -- this
    function only handles claim-type validity and entity resolution, not quote verification.
    The matching Evidence row is built separately via `build_evidence` (see
    curator.lit.run_extraction for how the two are assembled into one candidate).
    """
    raw_type = candidate.get("claim_type", "")
    try:
        claim_type = ClaimType(raw_type)
    except ValueError:
        return RejectedCandidate(reason=f"unknown claim_type {raw_type!r}", raw=candidate)

    if claim_type not in SUPPORTED_CLAIM_TYPES:
        return RejectedCandidate(
            reason=f"claim_type {claim_type.value!r} is not extracted by this pipeline yet", raw=candidate
        )

    subject_types, object_types = CLAIM_SIGNATURE[claim_type]
    subject = candidate.get("subject") or {}
    obj = candidate.get("object") or {}

    subject_id = _resolve_mention(subject, subject_types, entities=entities, crop=crop)
    if subject_id is None:
        return RejectedCandidate(reason=f"could not resolve subject {subject!r}", raw=candidate)

    if object_types & NEW_ENTITY_TYPES:
        return RejectedCandidate(
            reason=(
                f"{claim_type.value} needs a new {next(iter(object_types)).value} entity "
                "(props, sensor-variable mapping) built by hand -- extraction and grounding "
                "passed, but entity construction is out of scope for this pass"
            ),
            raw=candidate,
        )

    object_id = _resolve_mention(obj, object_types, entities=entities, crop=crop)
    if object_id is None:
        return RejectedCandidate(reason=f"could not resolve object {obj!r}", raw=candidate)

    qualifiers = candidate.get("qualifiers") or {}
    try:
        return Claim(type=claim_type, subject_id=subject_id, object_id=object_id, qualifiers=qualifiers)
    except Exception as exc:  # pydantic ValidationError or similar
        return RejectedCandidate(reason=f"claim failed schema validation: {exc}", raw=candidate)


def _resolve_mention(
    mention: dict[str, Any], allowed_types: frozenset[EntityType], *, entities: list, crop: Crop | str
) -> str | None:
    text = mention.get("text", "")
    if not text:
        return None
    for entity_type in allowed_types:
        try:
            if entity_type == EntityType.DISEASE:
                resolved = resolve_disease(text, crop)
            else:
                resolved = resolve_entity_from_bundle(text, entity_type, entities, crop)
        except AmbiguousName:
            return None
        if resolved is not None:
            return resolved
    return None


def build_evidence(
    claim_id: str, *, source_id: str, method: EvidenceMethod, extractor: str, locator: str, quote: str
) -> Evidence:
    return Evidence(
        claim_id=claim_id,
        source_id=source_id,
        method=method,
        extractor=extractor,
        locator=locator,
        quote=quote,
    )
