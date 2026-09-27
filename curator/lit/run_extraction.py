"""Orchestrate one paper through the search -> LLM extraction -> grounding -> normalization chain.

This is the smallest end-to-end slice that proves the Phase 5 v2 chain works: it does NOT write
anything into kg/curated/ automatically. A human reads ExtractionResult, checks the accepted
candidates the same way every source in this project has been checked by hand so far, and pastes
them into a curated YAML file. See curator/cli.py's `lit extract` subcommand for the CLI wrapper.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from curator.extract.ground import ground_candidate
from curator.extract.normalize import RejectedCandidate, build_claim_candidate
from curator.graph.bundle import KGBundle
from curator.graph.kg_files import load_curated_dir
from curator.graph.variety_import import variety_bundle
from curator.graph.vocab_entities import reference_bundle
from curator.lit import europepmc, jats
from curator.llm.client import LLMClient
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


def _strip_markdown_fence(content: str) -> str:
    """Strip a ```json ... ``` (or bare ``` ... ```) wrapper if present.

    The prompt explicitly says "no markdown fences" -- but a real full-paper run (PHASES.md item 33,
    31,939 characters of input, far longer than any of the 5 abstract-only pilot papers) got one
    anyway despite otherwise producing a complete, well-formed JSON array. Stripping defensively
    rather than rejecting a response that's actually fine is worth more than enforcing the letter of
    an instruction the model didn't follow."""
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = stripped[3:]
        if stripped.lstrip().startswith("json"):
            stripped = stripped.lstrip()[4:]
        if stripped.endswith("```"):
            stripped = stripped[:-3]
    return stripped.strip()


def _current_bundle() -> KGBundle:
    """Same composition as curator.cli._build_bundle() -- entities to resolve candidates against."""
    from curator.cli import KG_CURATED_DIR

    return KGBundle.merge(reference_bundle(), variety_bundle(), load_curated_dir(KG_CURATED_DIR))


def _retry_candidate(
    raw: dict, reason: str, *, source_text: str, llm_client: LLMClient, model: str | None
) -> dict | None:
    """One corrective pass for a rejected candidate (claim_retry_v1.md): show the model its own
    mistake and the exact rejection reason, ask for one fixed JSON object or `null`. Never raises --
    a malformed or unusable retry response just means "no fix", falling back to the original
    rejection, the same way every other malformed-LLM-output path in this file already behaves."""
    retry_prompt = _load_prompt("claim_retry_v1")
    user_message = (
        f"SOURCE TEXT:\n{source_text}\n\n"
        f"CANDIDATE THAT WAS REJECTED:\n{json.dumps(raw)}\n\n"
        f"REJECTION REASON:\n{reason}"
    )
    response = llm_client.complete(retry_prompt, user_message, model=model)
    try:
        parsed = json.loads(response.content)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


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
    retry: bool = False,
) -> ExtractionResult:
    """Fetch, verify, extract, ground, and normalize claims from one paper.

    `identifier` is "pmid:<digits>" or "doi:<doi>" (the same grammar curator.model.claims.Source
    requires). Raises europepmc.PublicationNotFound if the identifier doesn't resolve to a real
    paper -- there is no such thing as extracting from an unverified source in this pipeline.

    `prompt_version` selects curator/llm/prompts/<prompt_version>.md (default: claim_extraction_v1,
    the production prompt) -- overridable so eval/run_eval.py can run a real Phase 6.4 ablation
    between prompt variants without duplicating this function.

    `retry`: opt-in, off by default. When True, a candidate rejected by grounding or normalization
    gets one corrective pass (claim_retry_v1.md, curator.lit.run_extraction._retry_candidate) before
    being given up on. A claim accepted only after this pass gets "+retry" appended to its
    Evidence.extractor, so it's always visible as such rather than indistinguishable from a
    first-try success. Default False keeps every existing caller's behavior (and every existing
    test in tests/test_lit_run_extraction.py) unchanged.
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
        fulltext_xml = europepmc.fetch_fulltext_xml(metadata.pmcid)
        if fulltext_xml:
            try:
                text = jats.extract_plain_text(fulltext_xml)
            except ET.ParseError:
                text = None  # malformed XML -- fall back to the abstract below, don't send tag soup
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
    # `model=model` (not `model or DEFAULT_MODEL`) -- a real bug this shipped with: forcing
    # OpenRouter's DEFAULT_MODEL here overrode any other provider's own default whenever the
    # caller didn't name a model explicitly, so selecting "gemini"/"groq" silently made requests
    # for an OpenRouter-only model ID. Passing `None` through lets LLMClient.complete() resolve
    # its own provider-appropriate default instead.
    response = client.complete(system_prompt, text, model=model)

    try:
        raw_candidates = json.loads(_strip_markdown_fence(response.content))
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

    def _ground_and_build(raw: dict, *, extractor_tag: str = extractor) -> AcceptedCandidate | RejectedCandidate:
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
            return RejectedCandidate(reason=grounding.reason or "grounding failed", raw=raw)

        built = build_claim_candidate(raw, entities=entities, crop=crop)
        if isinstance(built, RejectedCandidate):
            return built

        claim = built
        method = _method_for(locator)
        evidence = Evidence(
            claim_id=claim.id,
            source_id=source.id,
            method=method,
            extractor=extractor_tag,
            locator=locator,
            quote=quote,
        )
        return AcceptedCandidate(claim=claim, evidence=evidence, grounding_score=grounding.score)

    for raw in raw_candidates:
        outcome = _ground_and_build(raw)
        if isinstance(outcome, AcceptedCandidate):
            result.accepted.append(outcome)
            continue

        if retry:
            corrected = _retry_candidate(
                raw, outcome.reason, source_text=text, llm_client=client, model=model
            )
            if corrected is not None:
                retried_outcome = _ground_and_build(corrected, extractor_tag=f"{extractor}+retry")
                if isinstance(retried_outcome, AcceptedCandidate):
                    result.accepted.append(retried_outcome)
                    continue
                outcome = RejectedCandidate(
                    reason=f"{outcome.reason} (retried: {retried_outcome.reason})", raw=raw
                )

        result.rejected.append(outcome)

    return result
