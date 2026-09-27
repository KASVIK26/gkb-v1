# Gold-standard annotation guidelines (Phase 6, RESEARCH_ROADMAP.md §6.1/§6.2)

**Purpose.** These rules define what a human (or a second, independently-prompted AI pass) writes
down as "the correct set of claims in this paper," so that `eval/run_eval.py` can compare it against
what `curator.lit.run_extraction.extract_paper` actually produced and report real precision, recall,
and hallucination numbers — not estimates.

**Status note (read this first).** As of 2026-09-27 this guideline has been piloted on 2 papers by a
single annotator (me, an AI). That is a pilot, not a gold standard: RESEARCH_ROADMAP.md §6.1/§6.2
call for ~45 papers, **double**-annotated by two independent people, with inter-annotator agreement
(Cohen's κ) reported before any precision/recall number from it is trusted. Nothing in
`eval/gold/wheat_pilot.jsonl` should be cited as "the gold standard" — it exists to prove the harness
itself works, and to catch guideline problems early (task 6.1's own acceptance criterion: "pilot on
5 papers, then revise").

---

## 1. Scope: only 6 claim types, on purpose

Annotate only the claim types `curator/extract/normalize.py`'s `SUPPORTED_CLAIM_TYPES` actually
extracts today. The KG's schema (`curator/model/enums.py`'s `ClaimType`) has 15 claim types total;
the other 9 (`VARIETY_RECOMMENDED_FOR_ZONE`, `GENE_PATHOTYPE_INTERACTION`, `GENE_LOCATED_AT`,
`QTL_ASSOCIATION`, `QTL_CONTAINS_REFGENE`, `MARKER_LINKAGE`, `PATHOTYPE_VARIANT_OF`,
`PATHOTYPE_PREVALENCE`, `VARIETY_DERIVED_FROM`) are real parts of the schema but nothing in the
pipeline extracts them from text yet — annotating them would only produce false "misses" the model
was never asked to find.

| Claim type | Subject → Object | Notes |
|---|---|---|
| `GENE_CONFERS_RESISTANCE` | Gene → Disease | |
| `VARIETY_CARRIES_GENE` | Variety → Gene | |
| `VARIETY_REACTION` | Variety → Disease | |
| `DISEASE_CAUSED_BY` | Disease → Pathogen | |
| `DISEASE_ENV_TRIGGER` | Disease → EnvTrigger | **object is always a brand-new entity** — see §2 |
| `DISEASE_MANAGED_BY` | Disease → Advisory | **object is always a brand-new entity** — see §2 |

## 2. A known, correct pipeline limitation — don't mistake it for a miss

`DISEASE_ENV_TRIGGER` and `DISEASE_MANAGED_BY` claims have an object that doesn't exist anywhere in
the KG's entity vocabulary yet (a numeric environmental threshold, or a management practice, is
always a *new* `EnvTrigger`/`Advisory` entity, never a lookup). `curator/extract/normalize.py`'s
`build_claim_candidate` deliberately routes these to "needs a human to build the entity" and rejects
them at the normalization step — the LLM found the fact and it passed grounding, but no `Claim`
object gets created, on purpose (this is how every env-trigger/advisory currently in
`kg/curated/env_triggers_v1.yaml` actually got in: a human read the paper and hand-built the entity).

**Still annotate these facts** (for recall measurement — did the LLM even find the sentence), but
`eval/run_eval.py` reports them under `gold_needs_human_entity`, separate from strict/relaxed
precision/recall, so the pipeline isn't penalized for a decision Phase 5 already made on purpose.

## 3. Required qualifiers per claim type

Straight from `curator/model/claims.py`'s `QUALIFIERS` dict — this is the actual validation the
`Claim` pydantic model runs, not a suggestion:

| Claim type | Required qualifiers | Optional qualifiers |
|---|---|---|
| `GENE_CONFERS_RESISTANCE` | `resistance_type`: one of `ASR` (all-stage/seedling), `APR` (adult-plant), `quantitative`, `unknown` | `spectrum` |
| `VARIETY_CARRIES_GENE` | `method`: one of `marker`, `sequence`, `haplotype`, `postulation`, `pedigree`, `stated` | `allele` |
| `VARIETY_REACTION` | `reaction`: one of `R`, `MR`, `I`, `MS`, `S`, `HS`; `stage`: one of `seedling`, `adult`, `unspecified` | `pathotype_id`, `location`, `season`, `n_locations`, `score_raw`, `scale` |
| `DISEASE_CAUSED_BY` | none | none |
| `DISEASE_ENV_TRIGGER` | none (the numeric condition itself goes in `notes`, not a qualifier — see §2) | none |
| `DISEASE_MANAGED_BY` | none (the practice itself goes in `notes` — see §2) | none |

`"unknown"`/`"unspecified"` are legitimate, honest values — use them when the text genuinely doesn't
say, rather than guessing. The one case with **no honest-unknown escape hatch**: if a
`VARIETY_REACTION` sentence gives no reaction class at all (R/MR/I/MS/S/HS), don't annotate a claim
— there's nothing to record.

**A bug this guideline caught, already fixed**: `claim_extraction_v1.md` originally told the model
to use `resistance_type` values `"race-specific"/"durable"/"QTL"`, but the real `ResistanceType`
enum is `ASR`/`APR`/`quantitative`/`unknown` — any claim following the prompt's own (wrong)
instruction would fail Pydantic validation and get silently rejected as `RejectedCandidate`, not
because the LLM found nothing, but because the prompt told it to emit an illegal value. Fixed in the
prompt 2026-09-27, before this guideline's pilot ran.

## 4. Quote rules (must match `curator/extract/ground.py` exactly)

A gold quote is judged by the same rule the pipeline enforces on itself, so a human annotation and a
model prediction are held to one standard:

1. **Verbatim substring of the real text you were given** (the same abstract or full-text XML
   `extract_paper` would fetch — see §6 for how to get the exact same text). Not a paraphrase, not a
   merge of two sentences.
2. **≥ 20 characters** (`MIN_QUOTE_CHARS` in `curator/model/claims.py`).
3. **Both the subject's and the object's surface text must appear inside the quote** (case-
   insensitive substring check, `ground.py`'s `entities_present`) — except when the object is an
   `EnvTrigger`/`Advisory` free-text description (§2), where only the subject's mention is required.

## 5. Edge cases (from `claim_extraction_v1.md`'s own rules — guideline and prompt must agree)

- **A citation to another paper is not this paper's own finding.** If a sentence cites another study
  for a number or result (a reference marker, "as reported by X et al."), don't annotate it.
- **Gene families are not genes.** "Sr genes", "Lr genes", "the Rpp loci" don't get a
  `GENE_CONFERS_RESISTANCE` claim — only a specific symbol (`Sr33`, `Rpp1`, `Rhg1-a`).
- **Ambiguous entity names.** If the paper's mention could resolve to more than one entity already
  in the KG (e.g. a gene symbol reused across crops, a variety name that collides with another),
  set `ambiguous: true` and leave `subject_id`/`object_id` as `null` rather than guessing — this
  mirrors `curator/normalize/synonyms.py`'s real `AmbiguousName` behavior, which the pipeline itself
  resolves by rejecting rather than guessing.
- **Unresolvable entities.** If the paper describes something not yet in the KG's vocabulary at all
  (a brand-new variety, a gene the catalogue doesn't have), still annotate the claim with
  `subject_id`/`object_id: null` — a gap in KG coverage is real signal, not something to hide by
  skipping the annotation.

## 6. Fetching the real text

Use `curator.lit.europepmc` directly (the exact functions `extract_paper` itself calls), not a
generic web search, so the gold quote is checked against the identical text the pipeline saw:

```python
from curator.lit import europepmc
record = europepmc.get_record("pmid:19229000")
metadata = europepmc.metadata_from_record(record, "pmid:19229000")
text = None
if metadata.is_open_access and metadata.pmcid:
    text = europepmc.fetch_fulltext_xml(metadata.pmcid)
if not text:
    text = europepmc.abstract_from_record(record)
```

Record which one you actually got (`"full text"` or `"abstract"`) in the gold record's `section`
field — the pipeline's own grounding result depends on which text it saw, and precision/recall
should be interpreted against the same text, not "whatever the full paper says" if only the abstract
was actually available to the model.

## 7. Strict vs. relaxed matching (what `eval/run_eval.py` computes)

- **Strict**: `claim_type` + `subject_id` + `object_id` + `qualifiers` all equal (the same
  comparison `Claim.id`'s content hash already encodes — RESEARCH_ROADMAP.md §4.2).
- **Relaxed**: `claim_type` + `subject_id` + `object_id` equal, qualifiers ignored. A claim that got
  the fact right but one qualifier wrong (e.g. `resistance_type: "APR"` instead of `"ASR"`) counts
  as a relaxed true positive but a strict miss — both numbers matter, for different reasons: strict
  precision is what the KG would actually store; relaxed precision tells you whether the model finds
  the right facts at all, separate from getting every qualifier exactly right.

## 8. Gold record schema (`eval/gold/*.jsonl`, one JSON object per line)

```json
{
  "source_id": "pmid:19229000",
  "claim_type": "GENE_CONFERS_RESISTANCE",
  "subject_text": "Lr34",
  "subject_id": "gene:wheat:Lr34",
  "object_text": "leaf rust",
  "object_id": "dis:wheat:leaf_rust",
  "qualifiers": {"resistance_type": "APR"},
  "quote": "Lr34 confers durable, adult-plant resistance to leaf rust (Puccinia triticina) in wheat.",
  "section": "abstract",
  "ambiguous": false,
  "annotator": "claude-pilot-2026-09-27",
  "notes": null
}
```

Field meanings match `eval/schema.py`'s `GoldClaim` model exactly — see that file for the
authoritative types.

**`source_id` must be the exact `pmid:`/`doi:` identifier** you'd pass to `extract_paper`/
`eval/run_eval.py --identifier`. A gold file may hold claims from several different papers (one
file per batch, or per crop); the harness filters to the matching `source_id` before scoring, so a
multi-paper gold file never penalizes recall for a fact that belongs to a different paper.
