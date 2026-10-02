# TASK FOR CHATGPT DEEP RESEARCH

You are running as a deep-research agent with browsing, PDF reading and (if available) a Python sandbox. **Do not ask clarifying questions** -
every parameter is specified below; where something is unclear, take the conservative option and say so in `note`.

How to use your strengths:
- **Open PDFs fully** and read tables page by page; AICRP and ICAR reports hide most facts in tables on page 40-200 of a long PDF. If you have
  a Python sandbox, download the PDF and extract tables programmatically, then **re-check each emitted quote against the extracted text**.
- When a table row carries the variety and the disease name only appears in the table header/caption, build the quote as
  `<caption or header fragment> ... <row fragment>` (see rule 2 and 3).
- Work source by source and write candidates as you go; do not hold everything until the end. Prefer 150 solid candidates to 400 doubtful ones.
- Where a document can be opened but is long, say in `source_log.csv` which page range you covered so that I can ask you to continue.
- Deliver Part A also as a downloadable `candidates.jsonl` file if your interface allows, **and** in the chat as code blocks.

---

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

Today's date: 2026-10-02.

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
{"work_order": "WO01", "date": "2026-10-02", "documents_opened": 0, "candidates": 0, "by_claim_type": {}, "skipped_for_ambiguity": 0,
 "known_limitations": ["..."]}
```

## 4. CLAIM TYPES YOU MAY EMIT

| claim_type | subject -> object | qualifiers (only these keys; omit what the source does not state) | typical evidence_basis |
|---|---|---|---|
| VARIETY_REACTION | Variety -> Disease | **reaction** R/MR/I/MS/S/HS, **stage** seedling/adult/unspecified, location, season (`2021-22` rabi, `2022` kharif), n_locations (int), score_raw, scale, pathotype_id (only an id from my list) | official_document, primary_field, primary_controlled |
| VARIETY_CARRIES_GENE | Variety -> Gene | **method** marker/sequence/haplotype/postulation/pedigree/stated, allele | primary_marker, primary_postulation, review_or_secondary |
| VARIETY_RECOMMENDED_FOR_ZONE | Variety -> AgroZone (a zone of THAT crop from the zone table in section 5; any other zone goes to leads) | season kharif/rabi/summer, sowing early/timely/late, water_regime irrigated/rainfed/restricted_irrigation | official_document |
| VARIETY_DERIVED_FROM | Variety -> Variety | **role** parent/selection_from/backcross_donor/recurrent_parent | official_document, primary_postulation |
| GENE_CONFERS_RESISTANCE | Gene -> Disease | **resistance_type** ASR (all-stage)/APR (adult-plant)/quantitative/unknown, spectrum (text) | primary_*, review_or_secondary |
| GENE_PATHOTYPE_INTERACTION | Gene -> Pathotype | **outcome** effective/defeated, year, region | primary_controlled, primary_field |
| QTL_ASSOCIATION | QTL -> Disease | stage, left_marker, right_marker, assembly, lod, p_value, pve_pct, population, n_env | primary_qtl, primary_gwas |
| MARKER_LINKAGE | Marker -> Gene or QTL | distance_cm, diagnostic (true/false) | primary_marker, primary_qtl |
| PATHOTYPE_VARIANT_OF | Pathotype -> Pathogen | (none) | any |
| PATHOTYPE_PREVALENCE | Pathotype -> AgroZone (a zone from section 5) | **years** [list of ints], frequency_pct | official_document, primary_field |
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

| id | name | also accepted |
|---|---|---|
| `dis:soybean:rust` | Soybean rust | Asian soybean rust |
| `dis:soybean:charcoal_rot` | Charcoal rot | - |
| `dis:soybean:frogeye_leaf_spot` | Frogeye leaf spot | - |
| `dis:soybean:anthracnose` | Anthracnose (pod blight) | - |
| `dis:soybean:pod_stem_blight` | Pod and stem blight | - |
| `dis:soybean:rhizoctonia_root_rot` | Rhizoctonia root rot | - |
| `dis:soybean:bacterial_pustule` | Bacterial pustule | - |
| `dis:soybean:mosaic_virus` | Soybean mosaic | - |
| `dis:wheat:stripe_rust` | Stripe rust | yellow rust |
| `dis:wheat:leaf_rust` | Leaf rust | brown rust |
| `dis:wheat:stem_rust` | Stem rust | black rust |
| `dis:wheat:powdery_mildew` | Powdery mildew | - |
| `dis:wheat:fusarium_head_blight` | Fusarium head blight | head scab, FHB |
| `dis:chickpea:fusarium_wilt` | Fusarium wilt | - |
| `dis:chickpea:dry_root_rot` | Dry root rot | - |
| `dis:chickpea:collar_rot` | Collar rot | - |
| `dis:chickpea:rust` | Chickpea rust | - |

Wheat synonyms the pipeline also understands: brown rust = leaf rust, black rust = stem rust, yellow rust = stripe rust.

**Pathogens** (ids for `props.pathogen`):

- `path:phakopsora_pachyrhizi` (Phakopsora pachyrhizi)
- `path:macrophomina_phaseolina` (Macrophomina phaseolina)
- `path:cercospora_sojina` (Cercospora sojina)
- `path:colletotrichum_truncatum` (Colletotrichum truncatum)
- `path:diaporthe_phaseolorum_var_sojae` (Diaporthe phaseolorum var. sojae)
- `path:rhizoctonia_solani` (Rhizoctonia solani)
- `path:xanthomonas_citri_pv_glycines` (Xanthomonas citri pv. glycines)
- `path:soybean_mosaic_virus_smv_potyvirus` (Soybean mosaic virus (SMV, Potyvirus))
- `path:puccinia_striiformis_f_sp_tritici` (Puccinia striiformis f. sp. tritici)
- `path:puccinia_triticina` (Puccinia triticina)
- `path:puccinia_graminis_f_sp_tritici` (Puccinia graminis f. sp. tritici)
- `path:blumeria_graminis_f_sp_tritici` (Blumeria graminis f. sp. tritici)
- `path:fusarium_graminearum_species_complex` (Fusarium graminearum species complex)
- `path:fusarium_oxysporum_f_sp_ciceris` (Fusarium oxysporum f. sp. ciceris)
- `path:athelia_rolfsii` (Athelia rolfsii)
- `path:uromyces_ciceris_arietini` (Uromyces ciceris-arietini)

**Zones** (`object.text` = the id's last part or the name; zones belong to ONE crop, and the same name is drawn differently per crop):

| zone id | name | also accepted | definition (from the KG's source) |
|---|---|---|---|
| `zone:chickpea:CZ` | Central Zone (chickpea) | Central Zone, CZ | cz- central zone |
| `zone:chickpea:MH` | MH (chickpea) | - | state-level zone |
| `zone:chickpea:MP` | MP (chickpea) | - | state-level zone |
| `zone:chickpea:NEPZ` | North Eastern Plain Zone (chickpea) | North Eastern Plain Zone, NEPZ | nepz-north eastern plain zone |
| `zone:chickpea:NHZ` | Northern Hills Zone (chickpea) | Northern Hills Zone, NHZ | nhz-northern hills zone |
| `zone:chickpea:NWPZ` | North Western Plain Zone (chickpea) | North Western Plain Zone, NWPZ | nwpz- north western plain zone |
| `zone:chickpea:SZ` | South Zone (chickpea) | South Zone, SZ | sz-south zone |
| `zone:soybean:CZ` | Central Zone (soybean) | Central Zone, CZ | M.P., Chhattisgarh, Rajasthan, Gujarat, Bundlekhand region of U.P. North-West Maharashtra |
| `zone:soybean:MH` | MH (soybean) | - | state-level zone |
| `zone:soybean:MP` | MP (soybean) | - | state-level zone |
| `zone:soybean:NEZ` | North Eastern Zone (soybean) | North Eastern Zone, NEZ | West Bengal, Odhissa, Assam, Sikkim, Arunachal Pradesh, Nagaland, Tripura, Meghalaya, Jharkhand and Eastern Bihar |
| `zone:soybean:NHZ` | North Hill Zone (soybean) | North Hill Zone, NHZ | Himachal Pradesh and Uttarakhand |
| `zone:soybean:NPZ` | North Plain Zone (soybean) | North Plain Zone, NPZ | Punjab, Haryana, Delhi, North east plains of U.P. and Western Bihar |
| `zone:soybean:SZ` | Southern Zone (soybean) | Southern Zone, SZ | Karnataka, A.P., Tamil Nadu, Kerala and Southern parts of Maharashtra |
| `zone:wheat:CZ` | Central Zone (wheat) | Central Zone, CZ | Madhya Pradesh, Chhattisgarh, Gujarat, Rajasthan (Kota and Udaipur divisions) and Uttar Pradesh (Jhansi division) |
| `zone:wheat:MH` | MH (wheat) | - | state-level zone |
| `zone:wheat:MP` | MP (wheat) | - | state-level zone |
| `zone:wheat:NEPZ` | North Eastern Plains Zone (wheat) | North Eastern Plains Zone, NEPZ | Eastern UP, Bihar, Jharkhand, Odisha, West Bengal and plains of Assam |
| `zone:wheat:NHZ` | Northern Hills Zone (wheat) | Northern Hills Zone, NHZ | Western Himalayan regions of J&K (except Jammu and Kathua distt.); Himachal Pradesh (except Una and Paonta valley); Uttarakhand (except Tarai area); Sikkim and hills of West Bengal and N.E. States |
| `zone:wheat:NWPZ` | North Western Plains Zone (wheat) | North Western Plains Zone, NWPZ | Punjab, Haryana, Delhi, Rajasthan (except Kota and Udaipur divisions) and Western UP (except Jhansi division), parts of J&K (Jammu and Kathua distt.) and parts of HP (Una distt. and Paonta valley) and Uttarakhand (Tarai region) |
| `zone:wheat:PZ` | Peninsular Zone (wheat) | Peninsular Zone, PZ | Maharashtra and Karnataka |

**Pathotype already present:** `pt:puccinia_graminis_f_sp_tritici:Ug99`.

**Varieties already in the KB** (use this spelling for `subject.text` when the source means the same variety):

- **chickpea** (36): Akash; BDNGK 798; Digvijay; JAKI 9218; JG 12; JG 14; JG 36; JGK 5; JGK-2; JGK-3; Jawahar Chana 6; Jawahar Gram 226; Jawahar Gram Kabuli 6; Kripa; PDKV Kanchan; PKV Harita; PKV Kabuli 4; Phule Vikram; Phule Vikrant; Pusa Chickpea 10216; Pusa Chickpea 20211; Pusa Parvati; Raj Vijay Gram 202; Raj Vijay Gram 203; Raj Vijay Gram 204; Raj Vijay Gram 205; Raj Vijay Gram 210; Raj Vijay Kabuli Gram 101; Raj Vijay Kabuli Gram 111; Raj Vijay Kabuli Gram 121; Raj Vijay Kabuli Gram 151; Raj Vijay Kabuli Gram 201; Raj Vijay Kabuli Gram 2020; Rajas; Shubhra; Super Annigeri-1
- **soybean** (21): JS 20-116; JS 20-29; JS 20-34; JS 20-69; JS 335; JS 80-21; JS 93-05; JS 95-60; MACS 58; MAUS 612; MAUS 725; NRC 136; NRC 157; NRC 86; Parbhani Sona; Pratishta; RVS 2001-4; Raj Soya-18; Raj Soya-24; Samrudhi; Shakti
- **wheat** (50): AKAW 4627; AKW 1071; DBW 110; DBW 168; DWR 162; DWR 195; GW 273; GW 322; GW 366; HD 2278; HD 2781; HD 2833; HD 2864; HD 2932; HD 2987; HD 4728; HD3090; HI 1077; HI 1500; HI 1531; HI 1544; HI 1605; HI 385; HI 617; HI 8381; HI 8498; HI 8627; HI 8713; HI 8737; HI 8759; HUW 510; JNK-4W-184; JWS17; K 9644; MACS 3949; MACS 4028; MACS 6222; MACS 6478; MP 1203; MP 3173; MP 3288; MP 3336; MP 3465; MP 4010; NIAW 1415; NIAW 917; RAJ 4037; Raj 4238; UAS 304; UAS 375

**Genes already in the KB:** Ca_14301 (chickpea), Fhb1 (wheat), Fhb7 (wheat), Lr21 (wheat), Lr26 (wheat), Lr34 (wheat), Pm37 (wheat), Pm6 (wheat), Rcs3 (soybean), Rpp1 (soybean), Rpp2 (soybean), Rpp3 (soybean), Rsv1 (soybean), Rsv3 (soybean), Rsv4 (soybean), Rxp (soybean), Sr2 (wheat), Sr24 (wheat), Sr31 (wheat), Sr33 (wheat), Sr35 (wheat), Sr50 (wheat), Yr6NLR1 (wheat), Yr6NLR2 (wheat), Yr9 (wheat)

**Where the KB is thin right now** (prefer these when a source gives you a choice):

| disease | variety reactions | resistance genes | advisories |
|---|---|---|---|
| Chickpea rust (`dis:chickpea:rust`) | 0 | 0 | 1 |
| Anthracnose (pod blight) (`dis:soybean:anthracnose`) | 0 | 0 | 1 |
| Pod and stem blight (`dis:soybean:pod_stem_blight`) | 0 | 0 | 1 |
| Rhizoctonia root rot (`dis:soybean:rhizoctonia_root_rot`) | 0 | 0 | 1 |
| Frogeye leaf spot (`dis:soybean:frogeye_leaf_spot`) | 0 | 1 | 1 |
| Fusarium head blight (`dis:wheat:fusarium_head_blight`) | 0 | 2 | 1 |
| Bacterial pustule (`dis:soybean:bacterial_pustule`) | 2 | 1 | 1 |
| Soybean rust (`dis:soybean:rust`) | 0 | 3 | 1 |
| Collar rot (`dis:chickpea:collar_rot`) | 4 | 0 | 1 |
| Charcoal rot (`dis:soybean:charcoal_rot`) | 4 | 0 | 1 |
| Soybean mosaic (`dis:soybean:mosaic_virus`) | 0 | 3 | 2 |
| Powdery mildew (`dis:wheat:powdery_mildew`) | 0 | 3 | 2 |
| Stripe rust (`dis:wheat:stripe_rust`) | 3 | 4 | 2 |
| Dry root rot (`dis:chickpea:dry_root_rot`) | 9 | 0 | 2 |
| Fusarium wilt (`dis:chickpea:fusarium_wilt`) | 33 | 1 | 2 |
| Stem rust (`dis:wheat:stem_rust`) | 31 | 6 | 1 |
| Leaf rust (`dis:wheat:leaf_rust`) | 40 | 4 | 1 |

Total claims now: 333 (VARIETY_REACTION 126, VARIETY_RECOMMENDED_FOR_ZONE 114, GENE_CONFERS_RESISTANCE 28, DISEASE_MANAGED_BY 22, DISEASE_CAUSED_BY 17, DISEASE_ENV_TRIGGER 17, VARIETY_CARRIES_GENE 5, QTL_ASSOCIATION 1, GENE_PATHOTYPE_INTERACTION 1, PATHOTYPE_VARIANT_OF 1, GENE_LOCATED_AT 1).

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

### WO01 - Wheat disease-screening reactions from AICRP reports

Use `WO01` as the work order id in every candidate_id and in batch_id.

**Objective.** Per-variety reactions to the wheat diseases (stripe, leaf, stem rust, powdery mildew, Fusarium head blight) from the multi-location
disease-screening tables of the All India Coordinated Research Project on Wheat & Barley and the ICAR-IIWBR.

**Start here (verify the URLs; find the current ones if they moved).** `https://www.aicrpwheatbarleyicar.in/` (Progress Reports, Annual Reports, "Wheat varieties
notified" documents); `https://iiwbr.icar.gov.in/` (Annual Reports, Director's Reports, AICRP Wheat & Barley "Crop Improvement" and "Crop Protection"
reports, "Wheat Rust Surveillance" bulletins). Years: 2015-16 to the latest available.

**Extract.** `VARIETY_REACTION` rows where the table gives a categorical class or a class legend in the same document, for varieties **released/notified
in India** (HD, DBW, PBW, HI, MP, MACS, GW, UAS, DWR, WH, K, NIAW, AKAW, HUW, Raj, NW, KRL and similar), ideally those recommended for the Central Zone
or Peninsular Zone. Each (variety, disease, season, location set) is one candidate. `evidence_basis` = `official_document`. Also emit
`VARIETY_RECOMMENDED_FOR_ZONE` when a notified-varieties table names a zone (e.g. CZ, PZ, NWPZ) or Madhya Pradesh / Maharashtra, with the conditions (season, sowing, water regime). Use the AICRP zone when the document uses one, the state zone (MP/MH) when it names the state; do not convert between them.

**Skip.** Entries still in trial (coded lines like `DBW 2023-45`); numeric-only columns (list the table in leads); anything not a wheat disease in scope.

**Target.** Up to ~250 candidates (expected ~150 accepted).
**Stop when.** You have covered the last 5 annual reports or run out of readable tables.
