"""Extraction + grounding via Google's LangExtract library, as an alternative to
curator.lit.run_extraction's custom single-shot prompt + rapidfuzz grounding.

Why this exists (PHASES.md item 33): three independent fixes to the custom pipeline's prompt
(rule edits, few-shot examples, a corrective retry pass) all failed to reliably prevent a recurring
class of failure -- a real fact stated indirectly (across two sentences, or via the pathogen name
instead of the disease name) gets a quote that doesn't literally contain the entity it needs, and
gets rejected. LangExtract solves the grounding half of this properly: it aligns each extraction to
an exact character interval in the source text (`char_interval`, `alignment_status`) rather than a
single fuzzy pass/fail score, and supports multiple extraction passes pooled together to improve
recall -- both are real, maintained implementations of ideas this project would otherwise have to
build and debug itself (see the research summary that led here).

This module does NOT replace curator.extract.normalize -- entity resolution to canonical KG IDs
stays exactly as it is (never trust a free-text attribute as a final ID; `build_claim_candidate`
already enforces that). LangExtract only replaces the "get a well-grounded (quote, claim-shape)
candidate out of an LLM" step; everything downstream is identical to the custom pipeline, so
`ExtractionResult`/`AcceptedCandidate`/`RejectedCandidate` are the same shapes staging, the review
app, and eval/run_eval.py already understand.
"""

from __future__ import annotations

import os

import langextract as lx
from langextract.factory import ModelConfig

from curator.extract.ground import entities_present
from curator.extract.normalize import RejectedCandidate, build_claim_candidate
from curator.graph.bundle import KGBundle
from curator.lit import europepmc, jats
from curator.lit.run_extraction import AcceptedCandidate, ExtractionResult, _current_bundle, _method_for
from curator.llm.client import NVIDIA_DEFAULT_MODEL
from curator.model.claims import Evidence, Source
from curator.model.enums import Crop, SourceType

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"  # OpenAI SDK base_url (no /chat/completions
#                                                            suffix -- the SDK appends that itself,
#                                                            unlike curator.llm.client's raw urllib
#                                                            NVIDIA_URL, which is the full endpoint).
_PIPELINE_VERSION = "langextract_v1"

# Alignment quality -> a 0-100 "grounding score" for consistency with the custom pipeline's
# AcceptedCandidate.grounding_score contract (a continuous transparency signal for the reviewer,
# not itself the accept/reject gate -- char_interval presence plus entities_present() are).
_ALIGNMENT_SCORE = {
    lx.data.AlignmentStatus.MATCH_EXACT: 100.0,
    lx.data.AlignmentStatus.MATCH_GREATER: 95.0,
    lx.data.AlignmentStatus.MATCH_LESSER: 90.0,
    lx.data.AlignmentStatus.MATCH_FUZZY: 80.0,
}

_PROMPT_DESCRIPTION = (
    "Extract every well-supported factual claim about gene resistance, variety disease reactions, "
    "environmental infection/spread conditions, or disease management practices that the text "
    "states as its own finding -- not a citation to a different paper, not background context, not "
    "a hedge. For each claim, extraction_text must be the exact verbatim sentence(s) (adjacent "
    "sentences may be combined) that state the fact. attributes must include subject_type, "
    "subject_text, object_type, object_text using the exact wording from extraction_text, plus any "
    "qualifiers that apply (resistance_type, reaction, stage, method, action_type, etc.) -- omit a "
    "qualifier you cannot support from the text rather than guessing. Never invent a parenthetical "
    "abbreviation or expansion that isn't literally in the quoted text. For GENE_CONFERS_RESISTANCE, "
    "object_type is always Disease, never Pathogen, even if the quoted sentence names the pathogen. "
    "If a sentence lists several diseases, emit one separate extraction per disease."
)

# Few-shot examples, each one a real pattern this project diagnosed and fixed or failed to fix via
# prompt-only changes this session (PHASES.md items 29-31) -- not fresh guesses.
_EXAMPLES = [
    # Cross-sentence disease reference (Lr34's real failure pattern, generalized).
    lx.data.ExampleData(
        text=(
            "Bacterial blight is a major disease of rice caused by Xanthomonas oryzae. Xa21 has "
            "conferred resistance to this pathogen in multiple genetic backgrounds since its discovery."
        ),
        extractions=[
            lx.data.Extraction(
                extraction_class="GENE_CONFERS_RESISTANCE",
                extraction_text=(
                    "Bacterial blight is a major disease of rice caused by Xanthomonas oryzae. Xa21 has "
                    "conferred resistance to this pathogen in multiple genetic backgrounds since its discovery."
                ),
                attributes={
                    "subject_type": "Gene", "subject_text": "Xa21",
                    "object_type": "Disease", "object_text": "Bacterial blight",
                    "resistance_type": "unknown",
                },
            )
        ],
    ),
    # Multi-disease sentence -> one extraction per disease, not a joined list.
    lx.data.ExampleData(
        text="Rpg1 has provided durable resistance to stem rust, leaf rust, and stripe rust in barley for over 70 years.",
        extractions=[
            lx.data.Extraction(
                extraction_class="GENE_CONFERS_RESISTANCE",
                extraction_text="Rpg1 has provided durable resistance to stem rust, leaf rust, and stripe rust in barley for over 70 years.",
                attributes={"subject_type": "Gene", "subject_text": "Rpg1", "object_type": "Disease", "object_text": disease, "resistance_type": "unknown"},
            )
            for disease in ("stem rust", "leaf rust", "stripe rust")
        ],
    ),
    # Never invent a parenthetical abbreviation not literally in the quote (Fhb1's real failure).
    lx.data.ExampleData(
        text="Fhb1 has been validated as a source of FHB resistance across environments.",
        extractions=[
            lx.data.Extraction(
                extraction_class="GENE_CONFERS_RESISTANCE",
                extraction_text="Fhb1 has been validated as a source of FHB resistance across environments.",
                attributes={
                    "subject_type": "Gene", "subject_text": "Fhb1",
                    "object_type": "Disease", "object_text": "FHB",
                    "resistance_type": "quantitative",
                },
            )
        ],
    ),
    # GENE_CONFERS_RESISTANCE's object is the disease, never the pathogen (Rcs3's real failure).
    lx.data.ExampleData(
        text="Frogeye leaf spot is caused by Cercospora sojina. Rcs3 confers resistance to all known races of C. sojina.",
        extractions=[
            lx.data.Extraction(
                extraction_class="GENE_CONFERS_RESISTANCE",
                extraction_text="Frogeye leaf spot is caused by Cercospora sojina. Rcs3 confers resistance to all known races of C. sojina.",
                attributes={
                    "subject_type": "Gene", "subject_text": "Rcs3",
                    "object_type": "Disease", "object_text": "Frogeye leaf spot",
                    "resistance_type": "unknown",
                },
            )
        ],
    ),
    lx.data.ExampleData(
        text="TestVariety1 carries TestGene2 based on marker-assisted screening in this study.",
        extractions=[
            lx.data.Extraction(
                extraction_class="VARIETY_CARRIES_GENE",
                extraction_text="TestVariety1 carries TestGene2 based on marker-assisted screening in this study.",
                attributes={
                    "subject_type": "Variety", "subject_text": "TestVariety1",
                    "object_type": "Gene", "object_text": "TestGene2", "method": "marker",
                },
            )
        ],
    ),
    lx.data.ExampleData(
        text="TestVariety1 was rated resistant to test blight at the adult-plant stage in this field trial.",
        extractions=[
            lx.data.Extraction(
                extraction_class="VARIETY_REACTION",
                extraction_text="TestVariety1 was rated resistant to test blight at the adult-plant stage in this field trial.",
                attributes={
                    "subject_type": "Variety", "subject_text": "TestVariety1",
                    "object_type": "Disease", "object_text": "test blight",
                    "reaction": "R", "stage": "adult",
                },
            )
        ],
    ),
    lx.data.ExampleData(
        text="Test blight developed rapidly when temperatures ranged between 20 and 25 degrees C with high humidity.",
        extractions=[
            lx.data.Extraction(
                extraction_class="DISEASE_ENV_TRIGGER",
                extraction_text="Test blight developed rapidly when temperatures ranged between 20 and 25 degrees C with high humidity.",
                attributes={
                    "subject_type": "Disease", "subject_text": "Test blight",
                    "object_type": "EnvTrigger",
                    "object_text": "temperatures between 20 and 25 degrees C with high humidity",
                },
            )
        ],
    ),
    lx.data.ExampleData(
        text="Test blight severity was reduced by two sprays of a fungicide at a 14-day interval in this trial.",
        extractions=[
            lx.data.Extraction(
                extraction_class="DISEASE_MANAGED_BY",
                extraction_text="Test blight severity was reduced by two sprays of a fungicide at a 14-day interval in this trial.",
                attributes={
                    "subject_type": "Disease", "subject_text": "Test blight",
                    "object_type": "Advisory",
                    "object_text": "two sprays of a fungicide at a 14-day interval",
                    "action_type": "chemical",
                },
            )
        ],
    ),
]


def _extraction_to_raw(extraction) -> dict:
    attrs = dict(extraction.attributes or {})
    subject_text = attrs.pop("subject_text", "")
    subject_type = attrs.pop("subject_type", "")
    object_text = attrs.pop("object_text", "")
    object_type = attrs.pop("object_type", "")
    return {
        "claim_type": extraction.extraction_class,
        "subject": {"type": subject_type, "text": subject_text},
        "object": {"type": object_type, "text": object_text},
        "qualifiers": attrs,
        "evidence": {"quote": extraction.extraction_text},
    }


def extract_paper_langextract(
    identifier: str,
    *,
    crop: Crop | str,
    model: str = NVIDIA_DEFAULT_MODEL,
    api_key: str | None = None,
    base_url: str = NVIDIA_BASE_URL,
    extraction_passes: int = 3,
    bundle: KGBundle | None = None,
) -> ExtractionResult:
    """LangExtract-backed equivalent of curator.lit.run_extraction.extract_paper.

    Same verified-fetch discipline (europepmc), same JATS parsing for full text
    (curator.lit.jats), same downstream normalization (curator.extract.normalize) and output
    shape -- only the extraction+grounding step is different. `extraction_passes` (default 3,
    matching this project's own multi-sample-recall research finding) runs the same text through
    the model multiple times and pools distinct extractions, rather than the custom pipeline's
    single deterministic call.
    """
    record = europepmc.get_record(identifier)
    metadata = europepmc.metadata_from_record(record, identifier)
    source = Source(
        id=metadata.id, type=SourceType.PUBLICATION, title=metadata.title,
        year=metadata.year, venue=metadata.venue, verified=True,
    )

    text = None
    if metadata.is_open_access and metadata.pmcid:
        fulltext_xml = europepmc.fetch_fulltext_xml(metadata.pmcid)
        if fulltext_xml:
            try:
                text = jats.extract_plain_text(fulltext_xml)
            except Exception:
                text = None
    if not text:
        text = europepmc.abstract_from_record(record)
    if not text:
        return ExtractionResult(source=source, rejected=[
            RejectedCandidate(reason="no abstract or full text available from Europe PMC", raw={})
        ])

    key = api_key if api_key is not None else os.environ.get("NVIDIA_API_KEY", "")
    document = lx.extract(
        text_or_documents=text,
        prompt_description=_PROMPT_DESCRIPTION,
        examples=_EXAMPLES,
        config=ModelConfig(
            model_id=model, provider="openai",
            provider_kwargs={"api_key": key, "base_url": base_url},
        ),
        extraction_passes=extraction_passes,
        show_progress=False,
    )

    entities = (bundle or _current_bundle()).entities
    # "llm:" prefix, not "langextract:" -- Evidence.extractor's schema requires
    # ^(?:llm|parser|pipeline|manual):\S+$ (curator/model/claims.py), and this is still
    # fundamentally an LLM call, just orchestrated through LangExtract rather than a raw prompt.
    extractor = f"llm:{model}@{_PIPELINE_VERSION}"
    result = ExtractionResult(source=source)
    seen_claim_ids: set[str] = set()  # multi-pass extraction can yield duplicate extractions

    for extraction in document.extractions or []:
        raw = _extraction_to_raw(extraction)
        quote = extraction.extraction_text or ""

        if extraction.char_interval is None:
            result.rejected.append(RejectedCandidate(
                reason="LangExtract could not align this extraction to a real location in the source text", raw=raw,
            ))
            continue

        subject_text = raw["subject"]["text"]
        object_text = raw["object"]["text"]
        object_type = raw["object"]["type"]
        mentions = [subject_text] if object_type in ("EnvTrigger", "Advisory") else [subject_text, object_text]
        if mentions and not entities_present(quote, mentions):
            missing = [m for m in mentions if m and m.lower() not in quote.lower()]
            result.rejected.append(RejectedCandidate(
                reason=f"quote does not mention: {', '.join(missing)}", raw=raw,
            ))
            continue

        built = build_claim_candidate(raw, entities=entities, crop=crop)
        if isinstance(built, RejectedCandidate):
            result.rejected.append(built)
            continue

        if built.id in seen_claim_ids:
            continue  # a duplicate across extraction passes -- not a new fact, not a new rejection
        seen_claim_ids.add(built.id)

        evidence = Evidence(
            claim_id=built.id, source_id=source.id, method=_method_for(None),
            extractor=extractor, locator=None, quote=quote,
        )
        grounding_score = _ALIGNMENT_SCORE.get(extraction.alignment_status, 0.0)
        result.accepted.append(AcceptedCandidate(claim=built, evidence=evidence, grounding_score=grounding_score))

    return result
