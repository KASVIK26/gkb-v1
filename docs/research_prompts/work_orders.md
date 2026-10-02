# Work orders

Each `## WOnn | tool | title` section becomes one ready-to-paste prompt (`python tools/build_research_prompts.py`). Run them one at a time;
feed each output to `agrihub kg ingest-candidates` before starting the next, because the rejection report tells you what to tell the model to fix.
Yield figures are honest estimates of *accepted* claims, not candidates.

## WO01 | chatgpt | Wheat disease-screening reactions from AICRP reports

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

## WO02 | chatgpt | Chickpea and soybean disease reactions from AICRP reports

**Objective.** Per-variety reactions for chickpea (Fusarium wilt, dry root rot, collar rot, rust) and soybean (rust, charcoal rot, frogeye leaf spot, anthracnose,
pod and stem blight, Rhizoctonia root rot, bacterial pustule, soybean mosaic virus) from AICRP annual reports and variety-release proposals.

**Start here.** ICAR-IIPR, Kanpur (`https://iipr.icar.gov.in/`) - AICRP on Chickpea annual reports and "Pulses varieties" lists; ICAR-IISR, Indore
(`https://iisrindore.icar.gov.in/`) - AICRP on Soybean annual reports and "Soybean varieties"; DPD (`https://dpd.gov.in/`) pulses variety lists;
DAC&FW oilseeds (`https://oilseeds.dac.gov.in/`). Also PDFs from state agricultural universities' variety release proposals (JNKVV Jabalpur, RVSKVV
Gwalior/Sehore, MPKV Rahuri, PDKV Akola, VNMKV Parbhani).

**Extract.** `VARIETY_REACTION` where the document states a class for a released variety and a disease in scope; `VARIETY_RECOMMENDED_FOR_ZONE` (MP/MH).
Existing KB claims for these varieties come from only two lists, so a **second independent source** for the same (variety, disease) is as valuable as a new variety.

**Skip.** Pests (girdle beetle, stem fly), abiotic stress, Ascochyta blight, YMV/MYMV, "pod blight" without a pathogen, numeric-only screening tables (list them).

**Target.** Up to ~200 candidates (expected ~110 accepted).
**Stop when.** Last 5 annual reports covered.

## WO03 | chatgpt | Notified varieties: zones, release year, parentage

**Objective.** Complete the variety layer: every wheat, chickpea and soybean variety notified in India that is recommended for Madhya Pradesh or Maharashtra
(Central Zone / Peninsular Zone / state recommendations), with where and how it is recommended and its parentage.

**Start here.** Gazette of India notifications of the Central Sub-Committee on Crop Standards, Notification and Release of Varieties (`https://egazette.gov.in/`);
`https://seednet.gov.in/`; DAC&FW "Notified varieties" lists; IIWBR "wheat varieties notified in India"; DPD chickpea variety list; DOD soybean list; ICAR "Crop varieties"
publications; state seed corporation (MPSSCL, Mahabeej) variety lists.

**Extract.** (1) `VARIETY_RECOMMENDED_FOR_ZONE` -> the zone the document names (AICRP zone, or `MP`/`MH` when it names the state) with season/sowing/water_regime when stated. (2) `VARIETY_DERIVED_FROM` for each parent named in a
pedigree table (`role: parent`; `backcross_donor`/`recurrent_parent` only if the source says so), `evidence_basis` = `official_document`. New varieties: put
`props` with release_year, releasing_institute, notification, pedigree, market_type **only as stated**.

**Skip.** Varieties not recommended for MP/MH; pedigrees written as codes only you cannot resolve to variety names.

**Target.** Up to ~500 candidates (expected ~350 accepted). Run once per crop if the output gets long (say which crop in `batch_id`).
**Stop when.** Every notified variety for those two states is covered or the sources run out.

## WO04 | chatgpt | Resistance-gene catalogues -> gene-to-disease claims

**Objective.** Which named genes confer resistance to which in-scope disease, from curated catalogues and databases.

**Start here.** Komugi / Wheat gene catalogue (`https://shigen.nig.ac.jp/wheat/komugi/genes/`) and the Catalogue of Gene Symbols for Wheat (McIntosh et al., current
supplement); GrainGenes (`https://wheat.pw.usda.gov/GG3/`) gene pages; SoyBase (`https://www.soybase.org/`) for Rpp (rust), Rsv (SMV), Rcs genes; peer-reviewed reviews
of Fusarium wilt resistance genes in chickpea (foc1-foc5) and of Pm genes in wheat. Prefer the catalogue entry or a primary mapping/cloning paper over a review.

**Extract.** `GENE_CONFERS_RESISTANCE` with `resistance_type` (ASR/APR/quantitative/unknown) exactly as the source states ("seedling resistance" -> ASR,
"adult plant resistance" -> APR). One candidate per (gene, disease). Gene symbols exactly as catalogued (`Yr15`, `Lr34`, `Sr31`, `Pm3b`, `Rpp1`, `Rsv1`).
Include `props.chromosome` and `props.origin_species` for **new** genes when the entry states them. `evidence_basis` = `review_or_secondary` for catalogues and reviews,
`primary_qtl`/`primary_marker`/`primary_controlled` for original mapping/cloning papers.

**Skip.** Genes for diseases outside scope (Karnal bunt, Septoria, nematodes, Phytophthora); temporary designations without a catalogued symbol.

**Target.** ~300 candidates (expected ~220 accepted).
**Stop when.** All Yr, Lr, Sr, Pm and Fhb genes of the wheat catalogue plus the soybean and chickpea sets are covered.

## WO05 | chatgpt | Which varieties carry which resistance genes

**Objective.** `VARIETY_CARRIES_GENE` for Indian released varieties, from studies that tested the variety itself.

**Start here.** Europe PMC search (open access) for: "gene postulation" Indian wheat varieties; "linked markers" Lr34 Lr24 Sr2 Yr10 Yr15 "Indian wheat cultivars"; ICAR-IIWBR
papers on stem/leaf/stripe rust genes in released varieties; "popular Indian wheat varieties" rust resistance genes table; soybean Rpp/Rsv in Indian cultivars; chickpea foc
markers in released varieties.

**Extract.** `VARIETY_CARRIES_GENE` with `method` as the paper states (marker, postulation, pedigree, stated). `evidence_basis` = `primary_marker` / `primary_postulation`
for the paper's own test, `review_or_secondary` for a table compiled from other papers. Candidate text names variety AND gene in the quote.

**Skip - this is where mistakes happen.** Improved/introgression lines named after a variety ("HD 2932 + Lr34"); lines where the paper's own text contradicts another
paper about the same variety (emit both, set `note: conflicts_with:`); genes "possibly present"; gene combinations given only as the cross's donor.

**Target.** ~250 candidates (expected ~150 accepted).

## WO06 | chatgpt | QTL and marker claims

**Objective.** `QTL_ASSOCIATION` and `MARKER_LINKAGE` for in-scope diseases.

**Start here.** Europe PMC: reviews and primary papers on QTL for stripe rust (Yr QTL, "QYr"), leaf rust, stem rust, powdery mildew, FHB (Fhb1, Qfhs), Fusarium wilt of chickpea
("QTL-hotspot", Ca2/Ca4 regions), charcoal rot and rust in soybean (Rpp loci), SMV (Rsv). Prefer papers with a QTL table (flanking markers, LOD, PVE, population).

**Extract.** One `QTL_ASSOCIATION` per QTL x disease with `left_marker`, `right_marker`, `lod`, `pve_pct`, `population`, `n_env`, `stage` when the table gives them; new QTL needs
`props.trait`. `MARKER_LINKAGE` when a marker is reported linked to a named gene/QTL (`distance_cm` as stated, `diagnostic: true` only if the paper says diagnostic/perfect marker); new marker
needs `props.marker_type`. Quote = the table row (with caption fragment naming the disease).

**Skip.** QTL for yield/quality; diseases out of scope; QTL without a stated flanking marker or interval.

**Target.** ~300 candidates (expected ~200 accepted).

## WO07 | grok | Rust pathotypes in India: variants and prevalence

**Objective.** `PATHOTYPE_VARIANT_OF`, `PATHOTYPE_PREVALENCE` and `GENE_PATHOTYPE_INTERACTION` for wheat rusts in India and Central India.

**Start here.** ICAR-IIWBR rust surveillance and pathotype-distribution reports (annual); Indian Phytopathology / Journal of Mycology and Plant Pathology / Frontiers papers on Puccinia
striiformis pathotypes (78S84, 46S119, 110S119, 238S119, 31S0 ...), P. triticina pathotypes (77-5, 77-9, 104-2, 12-5 ...), P. graminis (Ug99 lineage, 11, 40A) in India; differential-set
papers listing which Yr/Lr/Sr genes are effective or defeated.

**Extract.** `PATHOTYPE_VARIANT_OF` (pathotype -> its Pathogen, new pathotype needs `props.pathogen`), `PATHOTYPE_PREVALENCE` (pathotype -> a zone from section 5 with `years` list; `frequency_pct` only if stated for that
state; national figures are NOT a state figure - put them in leads), `GENE_PATHOTYPE_INTERACTION` (`outcome` effective/defeated from the paper's own differential test or survey; `year`, `region` as stated).

**Skip.** Pathotype names that appear only in news/social posts; anything where the host gene is unnamed.

**Target.** ~250 candidates (expected ~150 accepted).

## WO08 | grok | Registered fungicides and official recommendations (advisories)

**Objective.** `DISEASE_MANAGED_BY` advisories with product, dose and timing from **official** recommendations.

**Start here.** CIB&RC, Ministry of Agriculture, "Major Uses of Pesticides registered under Section 9(3) of the Insecticides Act" (`https://cibrc.gov.in/`) - label claims for wheat rust, powdery mildew,
loose smut, soybean rust / frogeye / anthracnose, chickpea wilt / root rot / rust; ICAR institutes' "Package of Practices" and technical bulletins; IIWBR "Wheat Crop Protection" recommendations; IISR Indore
soybean production technology; IIPR chickpea production technology; MP and Maharashtra agriculture department advisories and SAU "Krishi Diary"/package of practices PDFs.

**Extract.** One advisory per (disease, product, dose, timing) with the full `advisory` block copied in the source's words and units. `evidence_basis` = `official_document`.
Seed treatments, foliar sprays, bio-agents (Trichoderma, Pseudomonas), cultural measures (sowing date, crop rotation, resistant variety recommendations) all count.

**Skip.** Pesticides not labelled for the in-scope disease; company brochures; recommendations for other regions unless the document states the region (put it in `advisory.region`).

**Target.** ~200 candidates (expected ~150 accepted).

## WO09 | grok | Advisories from field trials and extension (Malwa / Maharashtra)

**Objective.** `DISEASE_MANAGED_BY` from peer-reviewed field trials and extension publications that test a treatment against an in-scope disease in India.

**Start here.** Europe PMC / PubMed: fungicide efficacy trials (propiconazole, tebuconazole, trifloxystrobin, hexaconazole, carbendazim, thiram, mancozeb, azoxystrobin) on wheat rust/powdery mildew,
soybean rust/frogeye/anthracnose, chickpea wilt/root rots; Trichoderma/Pseudomonas bio-control trials; sowing-date and rotation studies; Indian Journal of Plant Protection, Legume Research,
Journal of Mycology and Plant Pathology, Soybean Research. State-university extension bulletins and KVK technology pages for Indore, Ujjain, Dewas, Sehore, Vidisha, Akola, Parbhani.

**Extract.** As WO08, but `evidence_basis` = `primary_field` for the paper's own trial (with `n_locations` if 2+), `review_or_secondary` for a review. The quote must contain the product, dose and the
disease. Put the trial site in `advisory.region`.

**Target.** ~200 candidates (expected ~120 accepted).

## WO10 | grok | Epidemiology: weather and disease (leads only)

**Objective.** Find papers that quantify temperature, humidity, leaf-wetness, soil moisture or rainfall thresholds for the in-scope diseases in India, **for human conversion into sensor triggers**.
This work order produces **no `candidates.jsonl`**: Part A is replaced by `triggers.jsonl`, one JSON object per line:

```json
{"disease": "wheat stripe rust", "crop": "wheat", "phase": "infection", "variable": "air temperature", "min": 5, "max": 15, "unit": "degC", "condition_text": "optimum 10-15 C with 8 h of leaf wetness", "stage_text": "tillering to heading", "source": {"kind": "publication", "pmid": "...", "title": "..."}, "locator": "Results", "quote": "exact words", "evidence_basis": "primary_controlled"}
```

`phase` = infection | sporulation | spread | survival | expression. Numbers only as printed; never convert units. Everything else (Parts B-D) is the same.

**Target.** ~120 trigger records.

## WO11 | both | Gap filler: weakest diseases first

**Objective.** Use section 5 ("where the KB is thin") to choose the diseases with the fewest claims and cover them across **all** claim types by the methods above (reactions, genes, advisories,
pathotypes). Run it after WO01-WO09 with the updated coverage table (`python tools/build_research_prompts.py` regenerates it from the live KB).

**Target.** ~150 candidates. Give `batch_id` = `WO11-<tool>-<date>`.

## WO12 | both | Independent re-check of a batch

**Objective.** Quality control, not discovery. I will paste up to 40 candidate lines from a batch another tool produced. For each: open the cited source yourself, confirm the quote is verbatim, the
named parties are in it, and the claim is what the quote says. Return one JSON line per input: `{"candidate_id":"...","verdict":"confirmed|quote_not_found|claim_not_supported|source_unreadable","detail":"..."}`.
Do not add or change candidates. Parts A-D are replaced by this single list.
