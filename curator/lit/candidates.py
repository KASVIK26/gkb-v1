"""Verify claim candidates produced OUTSIDE this repo (ChatGPT / Grok deep research, a student's spreadsheet)
and turn the ones that survive into a curated-YAML batch.

Nothing a language model says is trusted. For each candidate (one JSON object per line, see
docs/research_prompts/00_shared_spec.md) this module checks, in order:

  1. the source is real: a publication is looked up on Europe PMC and the title the model gave must match the
     registry's (the registry's title is what we store); an official document needs an http(s) URL we can read;
  2. the quote is verbatim in that source's text (curator.graph.quote_audit.check_quote, fragment-aware);
  3. both entities resolve unambiguously to entities already in the KG -- or, for varieties, genes and advisories
     only, are created from the candidate when no near-duplicate exists;
  4. the quote actually names the subject and the object, and (advisories) contains the product and dose;
  5. the claim passes the same pydantic validation every other claim does.

Outcome per candidate: `accepted` (all checks passed), `needs_review` (a person should look: fuzzy quote, a name
missing from the quote, a near-duplicate entity), `unverifiable` (the source text could not be read from here) or
`rejected` (a check failed). Accepted claims are written as `llm:` evidence, which the scoring layer discounts
until a person reviews them; the evidence method is capped by what the source can support (a review article can
only ever be `review_statement`).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from rapidfuzz import fuzz

from curator.extract.normalize import RejectedCandidate, build_claim_candidate
from curator.graph.bundle import KGBundle
from curator.graph.quote_audit import check_quote, fetch_source_text, fetch_url_text, normalise
from curator.lit import europepmc
from curator.lit.find_evidence import compile_term
from curator.model import Claim, Entity, Evidence, Source
from curator.model.claims import MIN_QUOTE_CHARS
from curator.model.entities import AdvisoryProps
from curator.model.enums import CLAIM_SIGNATURE, ClaimType, Crop, EntityType, EvidenceMethod, SourceType
from curator.normalize.ids import gene_id, gene_local, make_id, slugify, variety_id

# Claim types this tool will ingest. GENE_LOCATED_AT / QTL_CONTAINS_REFGENE point at reference-genome records that only
# the genome pipeline creates, so they are accepted only when those entities already exist.
INGESTABLE = frozenset(ClaimType)
STATE_NAMES = {"MP": ["Madhya Pradesh", "M.P."], "MH": ["Maharashtra"]}
MAX_QUOTE_CHARS = 700
TITLE_MATCH_MIN = 88  # rapidfuzz ratio between the model's title and the registry's
NEAR_DUPLICATE_MIN = 90  # a "new" variety/gene this close to an existing name is a person's call
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_]{2,60}$")
_PRODUCER_RE = re.compile(r"[^a-z0-9._-]+")

BASIS_TO_METHOD = {
    "official_document": EvidenceMethod.OFFICIAL_DOCUMENT,
    "primary_field": EvidenceMethod.FIELD_SINGLE_ENV,
    "primary_controlled": EvidenceMethod.CONTROLLED_ENV,
    "primary_qtl": EvidenceMethod.QTL_MAPPING,
    "primary_gwas": EvidenceMethod.GWAS,
    "primary_marker": EvidenceMethod.LINKED_MARKER,
    "primary_postulation": EvidenceMethod.POSTULATION_PEDIGREE,
    "review_or_secondary": EvidenceMethod.REVIEW_STATEMENT,
}


# ───────────────────────────── the wire format ─────────────────────────────
class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Mention(_Strict):
    text: str = Field(min_length=1)
    type: EntityType
    alias_in_quote: str | None = None  # how the quote itself names it when that is not the usual name, e.g. "FW"
    props: dict[str, Any] | None = None  # for a NEW Variety/Gene/QTL/Marker/Pathotype: its properties (see the spec)
    advisory: dict[str, Any] | None = None  # only for Advisory objects: the structured practice


class SourceRef(_Strict):
    kind: str  # "publication" | "official_document"
    pmid: str | None = None
    doi: str | None = None
    url: str | None = None
    title: str
    year: int | None = None
    doc_slug: str | None = None  # official documents only: lowercase id fragment, e.g. "icar_wheat_pop_2023"
    publisher: str | None = None


class Candidate(_Strict):
    candidate_id: str
    producer: str = "external"  # e.g. "chatgpt-deep-research", "grok-deepsearch"
    batch_id: str = "batch"
    crop: Crop
    claim_type: ClaimType
    subject: Mention
    object: Mention
    qualifiers: dict[str, Any] = {}
    source: SourceRef
    locator: str | None = None
    quote: str
    evidence_basis: str
    note: str | None = None


# ───────────────────────────── results ─────────────────────────────
@dataclass
class Outcome:
    candidate_id: str
    bucket: str  # accepted | needs_review | unverifiable | rejected
    reason: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class IngestResult:
    sources: dict[str, Source] = field(default_factory=dict)
    entities: dict[str, Entity] = field(default_factory=dict)
    claims: dict[str, dict[str, Any]] = field(default_factory=dict)  # claim id -> curated-YAML claim spec
    outcomes: list[Outcome] = field(default_factory=list)
    missing_entities: Counter = field(default_factory=Counter)

    def counts(self) -> dict[str, int]:
        return dict(sorted(Counter(o.bucket for o in self.outcomes).items()))

    def reasons(self) -> Counter:
        return Counter((o.bucket, o.reason.split(":")[0][:90]) for o in self.outcomes if o.bucket != "accepted")


class _Stop(Exception):
    def __init__(self, bucket: str, reason: str):
        self.bucket, self.reason = bucket, reason


# ───────────────────────────── the pipeline ─────────────────────────────
def process_candidates(
    lines: list[str],
    *,
    bundle: KGBundle,
    fetch_record: Callable[[str], dict] = europepmc.get_record,
    fetch_text: Callable[[str], str | None] = fetch_source_text,
    fetch_url: Callable[[str], str | None] = fetch_url_text,
) -> IngestResult:
    result = IngestResult()
    known_sources = {s.id for s in bundle.sources}
    entities = list(bundle.entities)
    records: dict[str, dict | None] = {}
    texts: dict[str, str | None] = {}

    for number, line in enumerate(lines, 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            result.outcomes.append(Outcome(f"line{number}", "rejected", f"malformed candidate: not JSON ({exc.msg})"))
            continue
        try:
            candidate = Candidate.model_validate(raw)
        except ValidationError as exc:
            cid = raw.get("candidate_id", f"line{number}") if isinstance(raw, dict) else f"line{number}"
            first = exc.errors()[0]
            result.outcomes.append(Outcome(str(cid), "rejected", f"malformed candidate: {'.'.join(map(str, first['loc']))} {first['msg']}"[:200]))
            continue
        try:
            outcome = _process_one(
                candidate, raw, result=result, bundle=bundle, entities=entities, known_sources=known_sources,
                records=records, texts=texts, fetch_record=fetch_record, fetch_text=fetch_text, fetch_url=fetch_url,
            )
        except _Stop as stop:
            outcome = Outcome(candidate.candidate_id, stop.bucket, stop.reason, raw)
        result.outcomes.append(outcome)
    return result


def _process_one(c: Candidate, raw: dict, *, result: IngestResult, bundle: KGBundle, entities: list, known_sources: set,
                 records: dict, texts: dict, fetch_record, fetch_text, fetch_url) -> Outcome:
    quote = c.quote.strip()
    if len(quote) < MIN_QUOTE_CHARS or len(quote) > MAX_QUOTE_CHARS:
        raise _Stop("rejected", f"quote length {len(quote)} outside {MIN_QUOTE_CHARS}-{MAX_QUOTE_CHARS}")
    if c.evidence_basis not in BASIS_TO_METHOD:
        raise _Stop("rejected", f"unknown evidence_basis {c.evidence_basis!r}")
    review_flags: list[str] = []

    # 1. the source is real ─────────────────────────────────────────────
    source, text, is_review = _verify_source(c, records, texts, fetch_record, fetch_text, fetch_url)

    # 2. the quote is verbatim ──────────────────────────────────────────
    if text is None:
        raise _Stop("unverifiable", "source text could not be read from here")
    status = check_quote(quote, text)
    if status == "missing":
        if source.type is SourceType.PUBLICATION and len(text) < 3000:
            raise _Stop("unverifiable", "only an abstract is readable and the quote is not in it")
        raise _Stop("rejected", "quote not found in the source text")
    if status == "fuzzy":
        review_flags.append("quote matches only approximately")

    # 3. entities ─────────────────────────────────────────────────────
    new_entities: list[Entity] = []
    working = entities + list(result.entities.values())
    subject_mention = _prepare_mention(c.subject, c, working, new_entities)
    object_mention = _prepare_mention(c.object, c, working + new_entities, new_entities)
    built = build_claim_candidate(
        {"claim_type": c.claim_type.value, "subject": {"text": subject_mention.text}, "object": {"text": object_mention.text},
         "qualifiers": c.qualifiers},
        entities=working + new_entities, crop=c.crop, supported=INGESTABLE,
    )
    if isinstance(built, RejectedCandidate):
        for side, mention in (("subject", subject_mention), ("object", object_mention)):
            if f"resolve {side}" in built.reason:
                result.missing_entities[f"{mention.type.value}: {mention.text}"] += 1
        raise _Stop("rejected", built.reason[:200])
    claim: Claim = built
    for q in ("pathotype_id",):
        if claim.qualifiers.get(q) and claim.qualifiers[q] not in {e.id for e in working + new_entities}:
            raise _Stop("rejected", f"qualifier {q} {claim.qualifiers[q]!r} is not an entity in the KG")

    # 4. the quote names what it is supposed to support ──────────────
    ids = {e.id: e for e in working + new_entities}
    aliases: list[str] = []
    for side, entity_id in (("subject", claim.subject_id), ("object", claim.object_id)):
        if side == "object" and c.object.type is EntityType.ADVISORY:
            continue  # an advisory's name is ours; what the quote must contain is its product and dose (below)
        entity = ids[entity_id]
        mention = c.subject if side == "subject" else c.object
        usual = [entity.name, *entity.synonyms, (subject_mention if side == "subject" else object_mention).text]
        if entity.type is EntityType.AGRO_ZONE:
            usual += [n for st in entity.props.get("states", []) for n in STATE_NAMES.get(st, [st])]
        if not _quote_names(quote, usual):
            if mention.alias_in_quote and _quote_names(quote, [mention.alias_in_quote]):
                aliases.append(f"{side} named '{mention.alias_in_quote}'")
            else:
                review_flags.append(f"quote does not name the {side} ({entity.name})")
    if c.object.type is EntityType.ADVISORY:
        for key in ("active_ingredient", "dose"):
            value = (c.object.advisory or {}).get(key)
            if value and re.sub(r"\s+", "", value.lower()) not in re.sub(r"\s+", "", normalise(quote)):
                review_flags.append(f"advisory {key} {value!r} is not in the quote")

    # 5. accept ───────────────────────────────────────────────────────
    method = _cap_method(BASIS_TO_METHOD[c.evidence_basis], source, is_review, claim)
    producer = _PRODUCER_RE.sub("-", c.producer.lower()).strip("-") or "external"
    evidence = Evidence(
        claim_id=claim.id, source_id=source.id, method=method, extractor=f"llm:{producer}@{_PRODUCER_RE.sub('-', c.batch_id.lower())}",
        locator=(f"{c.locator} [alias in quote: {'; '.join(aliases)}]" if aliases else c.locator), quote=quote,
    )
    if review_flags:
        return Outcome(c.candidate_id, "needs_review", "; ".join(review_flags), raw)
    if source.id not in known_sources:
        result.sources.setdefault(source.id, source)
    for entity in new_entities:
        result.entities.setdefault(entity.id, entity)
    spec = result.claims.setdefault(claim.id, {
        "type": claim.type.value, "subject": claim.subject_id, "object": claim.object_id,
        "qualifiers": dict(claim.qualifiers), "evidence": [],
    })
    if not any(e["source"] == evidence.source_id and e["quote"] == evidence.quote for e in spec["evidence"]):
        spec["evidence"].append({"source": evidence.source_id, "method": method.value, "locator": evidence.locator,
                                 "quote": evidence.quote, "extractor": evidence.extractor, "candidate_id": c.candidate_id})
    return Outcome(c.candidate_id, "accepted", "", raw)


# ───────────────────────────── helpers ─────────────────────────────
def _verify_source(c: Candidate, records, texts, fetch_record, fetch_text, fetch_url) -> tuple[Source, str | None, bool]:
    ref = c.source
    if ref.kind == "publication":
        identifier = f"pmid:{ref.pmid}" if ref.pmid else (f"doi:{ref.doi}" if ref.doi else None)
        if identifier is None or (ref.pmid and not ref.pmid.isdigit()):
            raise _Stop("rejected", "publication needs a numeric pmid or a doi")
        if identifier not in records:
            try:
                records[identifier] = fetch_record(identifier)
            except (europepmc.EuropePMCError, europepmc.PublicationNotFound):
                records[identifier] = None
        record = records[identifier]
        if record is None:
            raise _Stop("rejected", f"{identifier} not found on Europe PMC")
        meta = europepmc.metadata_from_record(record, identifier)
        if fuzz.ratio(_title_key(ref.title), _title_key(meta.title)) < TITLE_MATCH_MIN:
            raise _Stop("rejected", f"title mismatch: model said {ref.title[:70]!r}, registry says {meta.title[:70]!r}")
        # the registry's identifier and title are what we keep
        stored_id = f"pmid:{record['pmid']}" if record.get("pmid") else identifier
        source = Source(id=stored_id, type=SourceType.PUBLICATION, title=re.sub(r"<[^>]+>", "", meta.title).replace('"', "'"),
                        year=meta.year, venue=meta.venue,
                        url=f"https://doi.org/{record['doi']}" if record.get("doi") else f"https://pubmed.ncbi.nlm.nih.gov/{record.get('pmid')}/",
                        verified=True)
        if stored_id not in texts:
            texts[stored_id] = fetch_text(stored_id)
        pub_types = " ".join((record.get("pubTypeList") or {}).get("pubType", [])).lower()
        return source, texts[stored_id], "review" in pub_types
    if ref.kind == "official_document":
        if not (ref.url or "").startswith("http") or not ref.doc_slug or not _SLUG_RE.match(ref.doc_slug):
            raise _Stop("rejected", "official_document needs an http(s) url and a lowercase doc_slug")
        source_id = f"doc:{ref.doc_slug}"
        if source_id not in texts:
            texts[source_id] = fetch_url(ref.url)
        source = Source(id=source_id, type=SourceType.OFFICIAL_DOCUMENT, title=ref.title, year=ref.year,
                        venue=ref.publisher, url=ref.url, verified=True)
        return source, texts[source_id], False
    raise _Stop("rejected", f"source kind {ref.kind!r} is not auto-ingestable (publication and official_document only)")


def _near_duplicate(existing: str, proposed: str) -> bool:
    """Same name apart from spacing/punctuation, or very similar overall ('MACS 4028' / 'MACS 40280'). Numbered series
    (JG 12, JG 62; HD 2967, HD 2987) are different varieties, and the quote check already guarantees the proposed
    name is spelled in the source, so a one-character difference is not treated as a typo."""
    a, b = (re.sub(r"[^a-z0-9]", "", x.lower()) for x in (existing, proposed))
    return a == b or fuzz.ratio(a, b) >= NEAR_DUPLICATE_MIN


def _title_key(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", re.sub(r"<[^>]+>", "", title).lower()).strip()


def _cap_method(method: EvidenceMethod, source: Source, is_review: bool, claim: Claim) -> EvidenceMethod:
    """The evidence type cannot be stronger than the source allows."""
    if method is EvidenceMethod.OFFICIAL_DOCUMENT and source.type is not SourceType.OFFICIAL_DOCUMENT:
        return EvidenceMethod.REVIEW_STATEMENT if is_review else EvidenceMethod.FIELD_SINGLE_ENV
    if is_review and method is not EvidenceMethod.OFFICIAL_DOCUMENT:
        return EvidenceMethod.REVIEW_STATEMENT
    if method is EvidenceMethod.FIELD_SINGLE_ENV and (claim.qualifiers.get("n_locations") or 0) >= 2:
        return EvidenceMethod.FIELD_MULTI_ENV
    return method


def _quote_names(quote: str, names: list[str]) -> bool:
    return any(compile_term(n).search(quote) for n in names if n and len(n) >= 2)


def _prepare_mention(m: Mention, c: Candidate, known: list, new_entities: list) -> Mention:
    """Create a Variety / Gene / Advisory entity when the KG has none and nothing similar exists."""
    from curator.extract.normalize import _resolve_mention

    crop = c.crop.value
    allowed = CLAIM_SIGNATURE[c.claim_type][0 if m is c.subject else 1]
    if m.type not in allowed:
        raise _Stop("rejected", f"{m.type.value} cannot be the {'subject' if m is c.subject else 'object'} of {c.claim_type.value}")
    if _resolve_mention({"text": m.text}, frozenset({m.type}), entities=known + new_entities, crop=crop) is not None \
            and m.type is not EntityType.ADVISORY:
        return m
    if m.type is EntityType.ADVISORY:
        if m.advisory is None:
            raise _Stop("rejected", "advisory object needs an `advisory` block")
        try:
            props = AdvisoryProps.model_validate(m.advisory)
        except ValidationError as exc:
            raise _Stop("rejected", f"advisory block invalid: {str(exc)[:120]}") from exc
        digest = hashlib.sha1(json.dumps([m.text, m.advisory], sort_keys=True).encode()).hexdigest()[:6]
        local = f"{slugify(c.subject.text)[:30]}_{slugify(props.active_ingredient or props.action_type)[:30]}_{digest}"
        entity = Entity(id=make_id(EntityType.ADVISORY, local, crop), type=EntityType.ADVISORY, name=m.text[:140], crop=crop,
                        props=props.model_dump(exclude_none=True))
        if entity.id not in {e.id for e in known + new_entities}:
            new_entities.append(entity)
        return Mention(text=entity.name, type=m.type)
    if m.type is EntityType.AGRO_ZONE:
        zone = next((e for e in known if e.id == f"zone:{crop}:{m.text.strip().upper()}"), None)
        if zone is None:
            raise _Stop("rejected", f"zone {m.text!r} is not in the KG (state-level zones MP and MH only)")
        return Mention(text=zone.name, type=m.type)
    if m.type in AUTO_CREATE:
        pool = [e.name for e in known + new_entities if e.type is m.type and (e.crop is None or e.crop.value == crop)]
        close = [n for n in pool if _near_duplicate(n, m.text)]
        if close:
            raise _Stop("needs_review", f"new {m.type.value} {m.text!r} is very close to existing {close[0]!r}")
        new_entities.append(_new_entity(m, crop, known + new_entities))
        return m
    return m  # unresolved: build_claim_candidate will reject with the reason, and we log the missing entity


AUTO_CREATE = frozenset({EntityType.VARIETY, EntityType.GENE, EntityType.QTL, EntityType.MARKER, EntityType.PATHOTYPE})


def _new_entity(m: Mention, crop: str, known: list) -> Entity:
    """Build the entity a candidate introduces, from the candidate's own `props`; never invent a property."""
    name, props = m.text.strip(), dict(m.props or {})
    try:
        if m.type is EntityType.VARIETY:
            return Entity(id=variety_id(crop, name), type=m.type, name=name, crop=crop, props=props)
        if m.type is EntityType.GENE:
            return Entity(id=gene_id(crop, name), type=m.type, name=name, crop=crop, props={"symbol": name, **props})
        if m.type is EntityType.QTL:
            if "trait" not in props:
                raise _Stop("rejected", f"new QTL {name!r} needs props.trait")
            return Entity(id=make_id(EntityType.QTL, gene_local(name), crop), type=m.type, name=name, crop=crop, props=props)
        if m.type is EntityType.MARKER:
            if "marker_type" not in props:
                raise _Stop("rejected", f"new Marker {name!r} needs props.marker_type (KASP|SSR|STS|SNP|CAPS|SCAR|other)")
            return Entity(id=make_id(EntityType.MARKER, gene_local(name), crop), type=m.type, name=name, crop=crop, props=props)
        pathogen = props.pop("pathogen", None)
        if not pathogen or not any(e.id == pathogen and e.type is EntityType.PATHOGEN for e in known):
            raise _Stop("rejected", f"new Pathotype {name!r} needs props.pathogen set to an existing path:<slug> id")
        return Entity(id=f"pt:{pathogen.split(':', 1)[1]}:{gene_local(name)}", type=m.type, name=name,
                      props={"designation": name, **props})
    except (ValidationError, ValueError) as exc:
        raise _Stop("rejected", f"cannot create {m.type.value} {name!r}: {str(exc)[:140]}") from exc


# ───────────────────────────── output ─────────────────────────────
def to_curated_yaml(result: IngestResult, header: str) -> str:
    import yaml

    def _dump(obj: Any) -> str:
        return yaml.safe_dump(obj, sort_keys=False, allow_unicode=True, width=1000)

    doc = {
        "sources": [s.model_dump(mode="json", exclude_none=True) for s in result.sources.values()],
        "entities": [e.model_dump(mode="json", exclude_none=True, exclude_defaults=False) for e in result.entities.values()],
        "claims": [{**{k: v for k, v in spec.items() if k != "evidence"},
                    "evidence": [{k: v for k, v in ev.items() if v is not None} for ev in spec["evidence"]]}
                   for spec in result.claims.values()],
    }
    return "".join(f"# {line}\n" for line in header.splitlines()) + "\n" + _dump(doc)


def report_markdown(result: IngestResult) -> str:
    counts = result.counts()
    lines = ["# Candidate ingest report", "", f"Candidates: {sum(counts.values())}  |  " + "  |  ".join(f"{k}: {v}" for k, v in counts.items()), ""]
    lines += [f"New claims: {len(result.claims)}  |  new sources: {len(result.sources)}  |  new entities: {len(result.entities)}", ""]
    if result.reasons():
        lines += ["## Why candidates were not accepted", "", "| outcome | reason | n |", "|---|---|---|"]
        lines += [f"| {b} | {r} | {n} |" for (b, r), n in result.reasons().most_common()]
        lines.append("")
    if result.missing_entities:
        lines += ["## Entities the KG does not have (create these, or fix the spelling, then re-run)", ""]
        lines += [f"- {name} (x{n})" for name, n in result.missing_entities.most_common(60)]
        lines.append("")
    lines += ["## Next", "",
              "1. `agrihub kg review-sheet <this batch>.yaml` makes a spreadsheet with a random sample marked (max(10, 10 %), advisories over-represented).",
              "2. Someone who knows the crop fills `verdict` (OK / WRONG / UNSURE) and, for advisories, `local_fit`.",
              "3. `agrihub kg apply-review <batch>.yaml <sheet>.csv --reviewer \"Name\"` enforces the sample gate and writes the batch to kg/curated/.", ""]
    return "\n".join(lines) + "\n"
