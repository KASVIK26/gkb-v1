"""Orchestrate one paper through the search -> LLM extraction -> grounding -> normalization chain.

This is the smallest end-to-end slice that proves the Phase 5 v2 chain works: it does NOT write
anything into kg/curated/ automatically. A human reads ExtractionResult, checks the accepted
candidates the same way every source in this project has been checked by hand so far, and pastes
them into a curated YAML file. See curator/cli.py's `lit extract` subcommand for the CLI wrapper.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from curator.extract.ground import ground_candidate
from curator.extract.normalize import RejectedCandidate, build_claim_candidate
from curator.graph.bundle import KGBundle
from curator.graph.kg_files import load_curated_dir
from curator.graph.variety_import import variety_bundle
from curator.graph.vocab_entities import reference_bundle
from curator.lit import europepmc
from curator.llm.client import DEFAULT_MODEL, LLMClient
from curator.model.claims import Claim, Evidence, Source
from curator.model.enums import Crop, EvidenceMethod, SourceType

_PROMPT_VERSION = "claim_extraction_v1"


@dataclass
class AcceptedCandidate:
    claim: Claim
    evidence: Evidence
    grounding_score: float  # rapidfuzz partial_ratio (0-100) between the quote and the fetched text


@dataclass
class ExtractionResult:
    source: Source
    accepted: list[AcceptedCandidate] = field(default_factory=list)
    rejected: list[RejectedCandidate] = field(default_factory=list)


def _load_prompt(version: str) -> str:
    from pathlib import Path

    return Path(__file__).resolve().parents[1].joinpath(
        "llm", "prompts", f"{version}.md"
    ).read_text(encoding="utf-8")


def _current_bundle() -> KGBundle:
    """Same composition as curator.cli._build_bundle() -- entities to resolve candidates against."""
    from curator.cli import KG_CURATED_DIR

    return KGBundle.merge(reference_bundle(), variety_bundle(), load_curated_dir(KG_CURATED_DIR))


def _method_for(section: str | None) -> EvidenceMethod:
    """Default every automatically-extracted claim to the LOWEST evidence weight
    (review_statement, 0.35) regardless of section. The extractor cannot reliably tell a
    controlled-environment trial from a field trial from a review's own summary of one -- that
    judgment call belongs to the human reviewing this candidate before it goes into
    kg/curated/, exactly as it has been made by hand for every source so far this project. A
    reviewer who confirms it's the paper's own field/controlled-environment result should
    upgrade this field, never the other way around."""
    return EvidenceMethod.REVIEW_STATEMENT


def extract_paper(
    identifier: str,
    *,
    crop: Crop | str,
    llm_client: LLMClient | None = None,
    bundle: KGBundle | None = None,
    model: str | None = None,
    prompt_version: str | None = None,
) -> ExtractionResult:
    """Fetch, verify, extract, ground, and normalize claims from one paper.

    `identifier` is "pmid:<digits>" or "doi:<doi>" (the same grammar curator.model.claims.Source
    requires). Raises europepmc.PublicationNotFound if the identifier doesn't resolve to a real
    paper -- there is no such thing as extracting from an unverified source in this pipeline.

    `prompt_version` selects curator/llm/prompts/<prompt_version>.md (default: claim_extraction_v1,
    the production prompt) -- overridable so eval/run_eval.py can run a real Phase 6.4 ablation
    between prompt variants without duplicating this function.
    """
    record = europepmc.get_record(identifier)
    metadata = europepmc.metadata_from_record(record, identifier)
    source = Source(
        id=metadata.id,
        type=SourceType.PUBLICATION,
        title=metadata.title,
        year=metadata.year,
        venue=metadata.venue,
        verified=True,
    )

    text = None
    section = "abstract"
    if metadata.is_open_access and metadata.pmcid:
        text = europepmc.fetch_fulltext_xml(metadata.pmcid)
        if text:
            section = "full text"
    if not text:
        text = europepmc.abstract_from_record(record)

    if not text:
        return ExtractionResult(source=source, rejected=[
            RejectedCandidate(reason="no abstract or full text available from Europe PMC", raw={})
        ])

    version = prompt_version or _PROMPT_VERSION
    client = llm_client or LLMClient()
    system_prompt = _load_prompt(version)
    response = client.complete(system_prompt, text, model=model or DEFAULT_MODEL)

    try:
        raw_candidates = json.loads(response.content)
    except json.JSONDecodeError:
        return ExtractionResult(source=source, rejected=[
            RejectedCandidate(reason="LLM returned invalid JSON", raw={"content": response.content})
        ])
    if not isinstance(raw_candidates, list):
        return ExtractionResult(source=source, rejected=[
            RejectedCandidate(reason="LLM returned a non-array JSON value", raw={"content": response.content})
        ])

    entities = (bundle or _current_bundle()).entities
    extractor = f"llm:{response.model}@{version}"
    result = ExtractionResult(source=source)

    for raw in raw_candidates:
        evidence_block = raw.get("evidence") or {}
        quote = evidence_block.get("quote", "")
        locator = evidence_block.get("section", section)

        subject_text = (raw.get("subject") or {}).get("text", "")
        object_block = raw.get("object") or {}
        object_text = object_block.get("text", "")
        object_type = object_block.get("type", "")
        # Only require the object's literal text to appear in the quote for named entities --
        # a free-text env-trigger/advisory description won't repeat verbatim in its own quote.
        entity_mentions = [subject_text] if object_type in ("EnvTrigger", "Advisory") else [subject_text, object_text]

        grounding = ground_candidate(quote=quote, source_text=text, entity_mentions=entity_mentions)
        if not grounding.passed:
            result.rejected.append(RejectedCandidate(reason=grounding.reason or "grounding failed", raw=raw))
            continue

        built = build_claim_candidate(raw, entities=entities, crop=crop)
        if isinstance(built, RejectedCandidate):
            result.rejected.append(built)
            continue

        claim = built
        method = _method_for(locator)
        evidence = Evidence(
            claim_id=claim.id,
            source_id=source.id,
            method=method,
            extractor=extractor,
            locator=locator,
            quote=quote,
        )
        result.accepted.append(AcceptedCandidate(claim=claim, evidence=evidence, grounding_score=grounding.score))

    return result
