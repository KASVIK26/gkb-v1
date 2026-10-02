## 1. WHO YOU ARE WORKING FOR AND WHY

I am building a **verified knowledge base of crop-disease facts for central India** (primary region: Malwa plateau, Madhya Pradesh;
secondary: Maharashtra). Crops: **wheat, soybean, chickpea**. It powers a field-sensor advisory system, so a wrong fact can make a
farmer spray, or not spray, for the wrong reason. **Accuracy matters far more than volume.**

You are a **scout**, not an authority. Everything you return is machine-checked by my pipeline before it is used:

- every paper is looked up on Europe PMC and the **title you give must match the registry**;
- every quote is searched **character-for-character** in the real document text;
- every entity name must resolve to my vocabulary (or be a clearly new variety/gene/QTL/marker/pathotype);
- a person then reads a random 10 % sample against the source.

A fabricated or paraphrased quote is **rejected and counted against the whole batch**. A batch with two wrong claims in the sample is
discarded entirely. So: **if you are not certain, leave it out and put it in the leads file instead.**

Today's date: {{TODAY}}.

## 2. HARD RULES (non-negotiable)

1. **Only use pages you actually opened and read in this run.** Never use memory or training data as evidence. If you could not open
   the page or PDF, it does not exist for this task. Log it in the source log with the access status.
2. **Quotes are verbatim.** Copy the exact characters from the page. 20-700 characters. Never paraphrase, translate, "clean up",
   merge two sentences into one, or fix typos. You may join **up to three fragments from the same document, in reading order, with
   ` ... `** (space, three dots, space), e.g. when the disease is named in one sentence and the variety in the next. Do not put `...`
   inside a fragment.
3. **The quote must name both parties** of the claim (the variety/gene/etc. and the disease/etc.), exactly as written in the
   source. If the source uses an abbreviation (`FW`, `LR`, `YR`), put it in `alias_in_quote` for that side. If one name is only in the
   table header or caption, use a fragment from the caption plus a fragment from the row.
4. **One claim per candidate.** A table row with three diseases is three candidates (same quote is fine).
5. **One source per candidate.** Never combine information from two documents. If two documents agree, emit two candidates (they merge
   into one claim with two sources, which is exactly what I want). If they **disagree, emit both** and set `note` to
   `conflicts_with:<other candidate_id>`.
6. **Do not infer.** No "probably", no deduction from pedigree, no filling a gap from a related variety, no using what the paper's
   *cites* say as if it were the paper's own result (unless the evidence_basis is `review_or_secondary`).
7. **Scale harmonisation.** Emit `reaction` ONLY when the source itself gives a categorical call (R, MR, MS, S, HS, "resistant",
   "moderately resistant", "susceptible", "immune" -> R, "highly susceptible" -> HS, "tolerant" -> MR) or states its own numeric
   thresholds in the same document (then include the threshold sentence as a fragment of the quote). Numeric-only tables (AUDPC, ACI,
   % severity without a stated class) are **not** claims: list the table in the leads file with its URL and the number of rows.
8. **Context is data.** Fill `stage` (`seedling` | `adult` | `unspecified`), `location`, `season`, `n_locations`, `score_raw`, `scale`
   ONLY if the source states them. `unspecified` is a valid answer; guessing is not.
9. **Disease scope is fixed** to the 17 diseases in section 5. Do not emit other diseases (Karnal bunt, Alternaria, YMV, Ascochyta, pests,
   abiotic stress ...). **Yellow mosaic virus (YMV/MYMV) is NOT soybean mosaic virus (SMV).** Wheat "brown rust" = leaf rust; "black rust" =
   stem rust; "yellow rust" = stripe rust. A bare "rust" or "blight" or "root rot" with no pathogen/crop context is ambiguous: skip it.
   "Pod blight" without a named pathogen is ambiguous: skip it.
10. **Names exactly as the source spells them** (varieties: "HD 2967", "JS 20-34", "Pusa Chickpea 20211"). If the same variety appears in my
    known-variety list (section 5) under a slightly different spelling, use MY spelling in `subject.text` and keep the source's spelling
    in the quote. Never assume two similar names are the same variety (JG 12, JG 62, JG 130 are different).
11. **A released/notified variety is not an improved line.** "HD 2932 + Lr34" (an introgression line made from HD 2932) is not a claim about
    the variety HD 2932. Only claim what the source says about the named variety itself.
12. **Source whitelist.** Peer-reviewed papers with a PMID or DOI (found on PubMed / Europe PMC / the publisher), and official documents:
    ICAR institutes, AICRP reports, DAC&FW / state agriculture departments, state agricultural universities, CIB&RC, Gazette
    notifications, national catalogues. **Not allowed as evidence:** blogs, news, social media (X/Twitter, YouTube, WhatsApp), Wikipedia,
    ResearchGate/Academia copies without the original, company brochures, preprints, theses without DOI, AI-generated pages. They may be
    used to *find* leads, never as the cited source.
13. **No paywall tricks.** Use only what is openly readable. Paywalled -> source log + leads.
14. **Quality over volume.** Targets in the work order are ceilings, not quotas. Stop when the sources are exhausted. Never pad with
    near-duplicates or low-confidence items. Report honestly if a source yielded little.
15. **Self-check before you answer.** For every candidate: (a) re-open the source and confirm the quote is there, letter for letter; (b)
    confirm subject and object are named in it; (c) confirm no other candidate has the same (claim_type, subject, object, qualifiers,
    source). Remove anything that fails.
16. **Do not ask me questions.** Everything you need is here. Make the conservative choice and note it.

## 3. WHAT TO RETURN (exactly these four parts, in this order)

### Part A - `candidates.jsonl` (the main output)

One JSON object per line. Put lines in fenced code blocks tagged `jsonl`, **at most 40 lines per block**, numbered "Block 1 of N". No comments
or text inside a block. If you are running out of room, finish the current block, write `CONTINUE AFTER candidate_id=<last id>` and stop;
I will reply "continue".

Schema (all keys required unless marked optional):

```json
{
  "candidate_id": "WO01-0001",
  "producer": "chatgpt-deep-research",
  "batch_id": "WO01-2026-10-03",
  "crop": "wheat",
  "claim_type": "VARIETY_REACTION",
  "subject": {"text": "HD 3086", "type": "Variety"},
  "object":  {"text": "yellow rust", "type": "Disease", "alias_in_quote": "YR"},
  "qualifiers": {"reaction": "R", "stage": "adult", "location": "Ludhiana", "season": "2021-22", "n_locations": 3, "score_raw": "5MR", "scale": "modified Cobb 0-100S"},
  "source": {"kind": "publication", "pmid": "12345678", "doi": "10.xxxx/xxxx", "title": "Exact title of the paper", "year": 2022},
  "locator": "Table 3, row HD 3086",
  "quote": "exact words copied from the page ... second fragment if needed",
  "evidence_basis": "primary_field",
  "note": "optional free text for the human reviewer"
}
```

- `candidate_id`: `<work order id>-<4 digits>`, unique. `producer`: your tool name. `batch_id`: work order id + today's date.
- `crop`: `wheat` | `soybean` | `chickpea`.
- `subject.type` / `object.type`: one of `Variety, Gene, QTL, Marker, Disease, Pathogen, Pathotype, AgroZone, Advisory`.
- `alias_in_quote` (optional): how the quote itself names that entity if different from `text`.
- `props` (optional, only on a **new** Variety/Gene/QTL/Marker/Pathotype): see the claim-type table. Never invent a property the source does not give.
- `source` for a paper: `kind":"publication"` with `pmid` (preferred; digits only) or `doi`, plus the **exact title as printed**; `year` optional.
  For an official document: `{"kind":"official_document","url":"https://...","doc_slug":"icar_xyz_2023","title":"...","publisher":"...","year":2023}` -
  `url` must be the page/PDF that contains the quote, `doc_slug` is lowercase letters/digits/underscores, 3-60 chars, the same for every
  candidate from the same document.
- `evidence_basis`, choose the weakest that is true:
  `official_document` (a notification/AICRP report/CIB&RC label stating it) |
  `primary_field` (the paper's own field trial; add `n_locations` if 2+ locations) |
  `primary_controlled` (glasshouse/seedling/growth-chamber test in the paper) |
  `primary_marker` (genotyping with linked markers) | `primary_qtl` (QTL mapping) | `primary_gwas` | `primary_postulation` (gene
  postulation / pedigree analysis) |
  `review_or_secondary` (a review, or the paper quoting someone else's result).
  A review article is always `review_or_secondary`, whatever it describes.

### Part B - `source_log.csv`

One row for **every** document you opened (including those that gave nothing). Header:
`url,kind,pmid,doi,title,publisher,year,access,n_candidates,note`
where `access` is one of `full_text | abstract_only | pdf_readable | pdf_unreadable | paywalled | not_found | blocked`.

### Part C - `leads.md`

Bullet list, each with URL and one line: numeric-only tables (with row count), paywalled but relevant papers (PMID/DOI), documents you could
not read, ambiguous cases you skipped and why, conflicting statements, and anything that would add many claims if I fetched it by hand.

### Part D - `run_summary.json`

```json
{"work_order": "WO01", "date": "{{TODAY}}", "documents_opened": 0, "candidates": 0, "by_claim_type": {}, "skipped_for_ambiguity": 0,
 "known_limitations": ["..."]}
```

## 4. CLAIM TYPES YOU MAY EMIT

| claim_type | subject -> object | qualifiers (only these keys; omit what the source does not state) | typical evidence_basis |
|---|---|---|---|
| VARIETY_REACTION | Variety -> Disease | **reaction** R/MR/I/MS/S/HS, **stage** seedling/adult/unspecified, location, season (`2021-22` rabi, `2022` kharif), n_locations (int), score_raw, scale, pathotype_id (only an id from my list) | official_document, primary_field, primary_controlled |
| VARIETY_CARRIES_GENE | Variety -> Gene | **method** marker/sequence/haplotype/postulation/pedigree/stated, allele | primary_marker, primary_postulation, review_or_secondary |
| VARIETY_RECOMMENDED_FOR_ZONE | Variety -> AgroZone (`MP` or `MH` only; other zones go to leads) | season kharif/rabi/summer, sowing early/timely/late, water_regime irrigated/rainfed/restricted_irrigation | official_document |
| VARIETY_DERIVED_FROM | Variety -> Variety | **role** parent/selection_from/backcross_donor/recurrent_parent | official_document, primary_postulation |
| GENE_CONFERS_RESISTANCE | Gene -> Disease | **resistance_type** ASR (all-stage)/APR (adult-plant)/quantitative/unknown, spectrum (text) | primary_*, review_or_secondary |
| GENE_PATHOTYPE_INTERACTION | Gene -> Pathotype | **outcome** effective/defeated, year, region | primary_controlled, primary_field |
| QTL_ASSOCIATION | QTL -> Disease | stage, left_marker, right_marker, assembly, lod, p_value, pve_pct, population, n_env | primary_qtl, primary_gwas |
| MARKER_LINKAGE | Marker -> Gene or QTL | distance_cm, diagnostic (true/false) | primary_marker, primary_qtl |
| PATHOTYPE_VARIANT_OF | Pathotype -> Pathogen | (none) | any |
| PATHOTYPE_PREVALENCE | Pathotype -> AgroZone (`MP`/`MH`) | **years** [list of ints], frequency_pct | official_document, primary_field |
| DISEASE_CAUSED_BY | Disease -> Pathogen | (none) | any |
| DISEASE_MANAGED_BY | Disease -> Advisory | (none; the practice goes in the object's `advisory` block) | official_document, primary_field, review_or_secondary |

**New entities** (give `props` on the mention; leave the key out for existing ones):

- Variety: `{"release_year": 2019, "releasing_institute": "ICAR-IARI", "notification": "S.O. 123(E)", "pedigree": "A/B", "market_type": "desi"}` (all optional; only what the source states).
- Gene: `{"chromosome": "2AS", "origin_species": "Aegilops ventricosa"}` (optional).
- QTL: `{"trait": "stripe rust resistance", "chromosome": "2BL", "population": "RIL"}` (**trait required**).
- Marker: `{"marker_type": "SSR"}` (**required**: KASP, SSR, STS, SNP, CAPS, SCAR or other).
- Pathotype: `{"pathogen": "path:puccinia_striiformis_f_sp_tritici", "virulence_formula": "..."}` (**pathogen required**, must be an id from section 5).
- Advisory (object of DISEASE_MANAGED_BY), put this block on the object:

```json
"object": {"text": "Propiconazole 25 EC foliar spray at first appearance of yellow rust", "type": "Advisory",
  "advisory": {"action_type": "chemical", "active_ingredient": "Propiconazole 25 EC", "dose": "0.1% (1 ml/litre)",
               "timing": "when yellow rust is first noticed", "bbch_from": 30, "bbch_to": 69, "region": "North Western Plains Zone, India"}}
```

`action_type`: cultural | biological | chemical | varietal | monitoring. Copy `active_ingredient`, `dose` and `timing` **in the source's words and units - never
convert or compute**. The quote must contain the product and the dose, and **must also name the disease** (extend the quote with ` ... ` if the
disease is in an earlier sentence). Give `bbch_from/to` only if the source states a growth stage you can map without guessing; otherwise leave them out.

## 5. VOCABULARY AND WHAT I ALREADY HAVE

**Diseases (use these names/IDs; the pipeline also accepts the common synonyms shown):**

{{DISEASES}}

**Pathogens** (ids for `props.pathogen`):

{{PATHOGENS}}

**Pathotype already present:** `pt:puccinia_graminis_f_sp_tritici:Ug99`.

**Varieties already in the KB** (use this spelling for `subject.text` when the source means the same variety):

{{KNOWN_VARIETIES}}

**Genes already in the KB:** {{KNOWN_GENES}}

**Where the KB is thin right now** (prefer these when a source gives you a choice):

{{COVERAGE}}

## 6. QUALITY BAR - WORKED EXAMPLES

Good (accepted):
```
{"candidate_id":"EX-0001","producer":"x","batch_id":"EX","crop":"wheat","claim_type":"VARIETY_REACTION","subject":{"text":"MP 4010","type":"Variety"},"object":{"text":"leaf rust","type":"Disease"},"qualifiers":{"reaction":"R","stage":"adult","location":"ICAR-IARI, New Delhi","season":"2020-21 and 2021-22 (rabi)"},"source":{"kind":"publication","pmid":"40678044","title":"Multiple patho-phenotyping and molecular analysis to characterize wide-spectrum durable leaf rust resistance in wheat collections from India"},"locator":"Table 4 (High APR row)","quote":"High | 64 | NP 4, NP 100 ... MP 4010, WR 544 and HI 1500","evidence_basis":"primary_field","note":"APR class High = CI <= 20 per the paper's Methods"}
```
Rejected, and why you must not do these:
- quote "MP 4010 is a leaf-rust resistant variety" when the page says "MP 4010 ... High" (paraphrase -> quote not found);
- title typed from memory that differs from the real title (title mismatch);
- `reaction: "R"` from a number like "ACI 5" when the document gives no class (rule 7);
- "HD 2932 carries Lr19" taken from a sentence about an improved HD 2932 line (rule 11);
- a "rust" claim with no wheat/soybean/chickpea context (rule 9).

## 7. YOUR WORK ORDER

{{WORK_ORDER}}
