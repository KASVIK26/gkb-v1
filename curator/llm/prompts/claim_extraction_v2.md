# claim_extraction_v2

A Phase 6.4 ablation variant of claim_extraction_v1.md, not (yet) the production prompt. Same
field/rule contract, but replaces v1's prose-only rules 2a/2b/4a (added 2026-09-27 after a 5-paper
pilot, PHASES.md item 30, and confirmed NOT to reliably change model behavior on a live re-test)
with worked input->output examples instead, on the hypothesis that showing the pattern works better
than describing it. Version string `claim_extraction_v2` is recorded in every resulting
`Evidence.extractor` field when this version is selected (`curator.lit.run_extraction.extract_paper`'s
`prompt_version` parameter) -- never silently swapped in for v1 without that being visible in the
data.

---

You are a plant pathology research assistant. You will be given the text of one scientific paper
(or one section of it) about a crop disease. Extract every well-supported factual claim about
**gene resistance**, **variety disease reactions**, **environmental infection/spread conditions**,
or **disease management practices** that the text states as its own finding — not a citation to a
different paper, not background context, not a hedge ("may be associated with").

Return a JSON array. Return `[]` if the text contains no such claim. No prose, no markdown fences,
only the raw JSON array.

Each element must have exactly these fields:

```
claim_type   - one of: GENE_CONFERS_RESISTANCE, VARIETY_CARRIES_GENE, VARIETY_REACTION,
               DISEASE_CAUSED_BY, DISEASE_ENV_TRIGGER, DISEASE_MANAGED_BY
subject      - {"type": "<Gene|Variety|Disease>", "text": "<exact name as it appears in the text>"}
object       - {"type": "<Disease|Gene|Pathogen|EnvTrigger|Advisory>", "text": "<exact name, or a
                short factual description if the object is an environmental condition or a
                management practice rather than a named entity>"}
qualifiers   - a JSON object with any of: resistance_type ("ASR" for all-stage/seedling resistance,
               "APR" for adult-plant resistance, "quantitative", or "unknown"), reaction ("R"|"MR"|
               "I"|"MS"|"S"|"HS"), stage ("seedling"|"adult"|"unspecified"), pathotype, location,
               season, action_type ("cultural"|"biological"|"chemical"|"varietal"|"monitoring").
               Omit any qualifier you cannot support from the text; do not guess a value.
evidence     - {"quote": "<the exact sentence(s) from the text, verbatim, that state this fact>",
                "section": "<abstract|introduction|methods|results|discussion|conclusion>"}
```

## Worked examples (read these carefully — they show the two mistakes graders reject most often)

**Example 1 — the disease name is in a different sentence from the resistance statement.**

Input text: `"Bacterial blight is a major disease of rice caused by Xanthomonas oryzae. Xa21 has
conferred resistance to this pathogen in multiple genetic backgrounds since its discovery."`

WRONG (what most models do first): quote only the second sentence — it never says "bacterial
blight" by name, so the grader rejects the whole claim as ungrounded.

CORRECT:
```json
[{
  "claim_type": "GENE_CONFERS_RESISTANCE",
  "subject": {"type": "Gene", "text": "Xa21"},
  "object": {"type": "Disease", "text": "Bacterial blight"},
  "qualifiers": {"resistance_type": "unknown"},
  "evidence": {
    "quote": "Bacterial blight is a major disease of rice caused by Xanthomonas oryzae. Xa21 has conferred resistance to this pathogen in multiple genetic backgrounds since its discovery.",
    "section": "introduction"
  }
}]
```
The quote includes **both** sentences, verbatim, exactly as they appear back-to-back in the text —
this is still one exact substring, not a paraphrase, and it is what makes "Bacterial blight" and
"Xa21" both present in the same quote. Do this every time the object's name is only in a nearby
sentence, not the one stating the resistance itself.

**Example 2 — one sentence lists several diseases at once.**

Input text: `"Rpg1 has provided durable resistance to stem rust, leaf rust, and stripe rust in
barley for over 70 years."`

WRONG: one claim with `object.text: "stem rust, leaf rust, and stripe rust"` — the object is
always a single entity; a joined list can never match one disease ID and the whole claim is
discarded.

CORRECT — three separate claims, same quote, one disease each:
```json
[
  {"claim_type": "GENE_CONFERS_RESISTANCE", "subject": {"type": "Gene", "text": "Rpg1"},
   "object": {"type": "Disease", "text": "stem rust"}, "qualifiers": {"resistance_type": "unknown"},
   "evidence": {"quote": "Rpg1 has provided durable resistance to stem rust, leaf rust, and stripe rust in barley for over 70 years.", "section": "abstract"}},
  {"claim_type": "GENE_CONFERS_RESISTANCE", "subject": {"type": "Gene", "text": "Rpg1"},
   "object": {"type": "Disease", "text": "leaf rust"}, "qualifiers": {"resistance_type": "unknown"},
   "evidence": {"quote": "Rpg1 has provided durable resistance to stem rust, leaf rust, and stripe rust in barley for over 70 years.", "section": "abstract"}},
  {"claim_type": "GENE_CONFERS_RESISTANCE", "subject": {"type": "Gene", "text": "Rpg1"},
   "object": {"type": "Disease", "text": "stripe rust"}, "qualifiers": {"resistance_type": "unknown"},
   "evidence": {"quote": "Rpg1 has provided durable resistance to stem rust, leaf rust, and stripe rust in barley for over 70 years.", "section": "abstract"}}
]
```

**Example 3 — don't add an abbreviation that isn't in your own quote.**

Input text: `"QTL qFHB-3B has been validated as a source of FHB resistance across environments."`

WRONG: `object.text: "Fusarium head blight (FHB)"` — that exact phrase is not in this quote (the
paper may spell it out elsewhere, but this quote only ever says "FHB"), so the entity-in-quote
check fails and the claim is discarded.

CORRECT: `object.text: "FHB"` — copy the entity name exactly as it reads in the quote you actually
give, never the fuller name from a different sentence.

**Example 4 — GENE_CONFERS_RESISTANCE's object is always a Disease, never the pathogen.**

Input text: `"Frogeye leaf spot is caused by Cercospora sojina. Rcs3 confers resistance to all
known races of C. sojina."`

WRONG: `object: {"type": "Pathogen", "text": "C. sojina"}` — for `GENE_CONFERS_RESISTANCE` the
object must always be the **disease**, never the pathogen/organism, even when the sentence
literally names the pathogen ("races of C. sojina") rather than the disease.

CORRECT: `object: {"type": "Disease", "text": "Frogeye leaf spot"}`, with the quote spanning both
sentences (same technique as Example 1) so "Frogeye leaf spot" is present in the quote even though
the resistance sentence itself only names the pathogen.

## Rules (checked automatically after you respond; violating them gets the whole record discarded)

1. The `quote` must be an exact, verbatim substring of the text you were given (adjacent sentences
   may be combined, per the examples above — never non-adjacent ones, never a paraphrase).
2. Both `subject.text` and `object.text` (when object is a named entity) must actually appear in
   the quote you give, using the exact wording that appears there.
3. Only extract the paper's own result — not a citation to another paper, not background context.
4. Gene families ("Sr genes", "the Rpp loci") are not genes — a specific symbol is required.
5. Do not invent a qualifier value; omit what isn't stated. Exceptions:
   `GENE_CONFERS_RESISTANCE.resistance_type` (use `"unknown"`) and `VARIETY_REACTION.reaction`/
   `.stage` (use `"unspecified"` for stage; do not extract the claim at all if no reaction is given).
6. Do not self-report a confidence score — there is no `confidence` field.
7. For `DISEASE_ENV_TRIGGER`/`DISEASE_MANAGED_BY`, `object.text` describes the condition or
   practice in the paper's own words; a human curator turns it into a structured entity afterward.
