# Plan: from 333 to 3,000+ verified claims

Written 2026-10-02 against release `kg_2026_10_24` (333 claims, 73 sources, 216 entities; tiers A 223 / B 32 / C 42 / D 36).
Goal: **at least 3,000 claims in the live release, each with a source a machine has checked**, without lowering the bar that the
first 333 had to clear. Stretch: ~3,700.

## 1. Why the obvious route fails, and what we do instead

Step 4 (item 40 in `PHASES.md`) measured it: reading **paper by paper** (107 varieties searched across open-access full text, ~300 hits)
produced **12 usable claims**, a yield of about 4 %. At that rate 3,000 claims would take ~75,000 hits read by a person.

Yield comes from **documents that are already tables of facts**, where one PDF holds hundreds of rows:

| source family | what one document holds | yield |
|---|---|---|
| AICRP / ICAR annual reports (wheat, chickpea, soybean) | per-variety disease reactions across locations | 50-300 claims per report |
| Gazette / DAC&FW / IIWBR / DPD notified-variety lists | variety x zone x season, pedigree | 100-400 per list |
| Gene catalogues (Komugi, McIntosh supplements, GrainGenes, SoyBase) | gene -> disease, chromosome, origin | 200-300 in total |
| CIB&RC "Major Uses of Pesticides" + ICAR/SAU package of practices | disease x product x dose x timing | 150-250 |
| QTL / rust-pathotype tables in a few review papers | QTL intervals, pathotype x gene matrices | 150-300 per review |

So the plan is **scale the sources, not the reading**, and add two machines: an LLM *scout* that finds and transcribes (ChatGPT / Grok deep
research), and a *verifier* that decides what to believe (`agrihub kg ingest-candidates`). A model is never the authority.

## 2. The pipeline (built; see `curator/lit/candidates.py`)

```
 research prompt  ->  ChatGPT / Grok  ->  candidates.jsonl + source_log.csv + leads.md
        ^                                      |
        |                                      v
  "where the KB is thin"      agrihub kg ingest-candidates  (needs network)
  (regenerated from live KB)    1. paper exists on Europe PMC, title matches registry (we store the registry's)
                                2. quote is verbatim in the real text (fragment-aware, tables and captions included)
                                3. subject/object resolve to the KB, or a new Variety/Gene/QTL/Marker/Pathotype/Advisory is
                                   built only from properties the candidate states (near-duplicate names -> a person)
                                4. quote names both parties (alias allowed and recorded); advisory dose/product are in the quote
                                5. pydantic validation, evidence method capped by what the source allows (a review is always
                                   review_statement; field_multi_env needs n_locations >= 2)
                                      |
        accepted -> kg/incoming/<batch>.yaml + report with a random 10 % spot-check list
        needs_review / unverifiable / rejected -> .jsonl with the reason (the feedback for the next prompt)
                                      |
                       a person reads the sample against the sources
                       >= 95 % correct -> git mv into kg/curated/;  otherwise the batch is discarded
                                      |
              kg build -> kg verify-quotes (audit) -> kg load --release -> compare with live -> kg promote
```

Rules that keep volume honest:

- **Evidence is `llm:` until a person reviews it**, so the scoring layer applies its x0.6 discount to model-found evidence. An unreviewed
  model-found claim tops out at 0.9 x 0.6 = 0.54 (tier C) on one source and 0.79 (tier B) on two; **tier A needs a person's review**, never a model's say-so. The review app (Streamlit) is where `status` is flipped.
- **Claims are counted as distinct (type, subject, object, context)**. A second source for an existing claim improves its tier but does *not*
  count toward 3,000. Padding with near-duplicates is the failure mode this plan most needs to avoid.
- **Numeric-only tables are not claims.** They go to a leads list; harmonising ACI/AUDPC into R/MS/S is a separate, documented step (Phase 7),
  not something a prompt may improvise.
- **Ambiguity is dropped, not guessed** (YMV is not SMV; "pod blight" names no pathogen; an improved line is not its parent variety).

## 3. Budget by claim type

Targets are *accepted* claims. "Yield" columns are estimates and will be corrected after the first runs; the prompts recompute coverage each time.

| claim type | now | add | via | work order | main risk |
|---|---|---|---|---|---|
| VARIETY_REACTION | 126 | +900 | AICRP screening tables, release proposals | WO01, WO02 | scale harmonisation, stale resistance |
| VARIETY_RECOMMENDED_FOR_ZONE | 114 | +450 | notified-variety lists | WO01-03 | only MP/MH zones exist; AICRP zones need vocab (Phase 0) |
| VARIETY_DERIVED_FROM | 0 | +200 | pedigree tables | WO03 | code-only pedigrees |
| GENE_CONFERS_RESISTANCE | 28 | +300 | gene catalogues | WO04 | symbol drift, diseases out of scope |
| VARIETY_CARRIES_GENE | 5 | +250 | postulation / linked-marker studies | WO05 | improved lines mistaken for varieties |
| QTL_ASSOCIATION + MARKER_LINKAGE | 2 | +300 | QTL tables | WO06 | intervals without markers |
| PATHOTYPE_* + GENE_PATHOTYPE_INTERACTION | 2 | +300 | rust surveillance, differential sets | WO07 | national vs state figures |
| DISEASE_MANAGED_BY (advisories) | 22 | +250 | CIB&RC, ICAR/SAU, trials | WO08, WO09 | dose/units, region transfer |
| DISEASE_ENV_TRIGGER | 17 | +60 | epidemiology papers, entities built by hand | WO10 | needs a person to build each trigger |
| DISEASE_CAUSED_BY + other | 17 | +30 | pathogen catalogues | WO11 | - |
| **Total** | **333** | **~3,040** | | | **~3,370 live** |

## 4. Schedule

| step | what | cumulative claims | gate before the next step |
|---|---|---|---|
| 0 | Vocabulary: add AICRP zones (CZ, PZ, NWPZ, NEPZ, NHZ, SZ) and the pathogens still missing; run the ingest tool on the 5-line example; dry-run WO03 on one crop | 333 | tool and prompt behave on real output; rejection reasons understood |
| 1 | WO03 (varieties, zones, pedigree), WO04 (gene catalogues) | ~1,100 | 10 % sample >= 95 % correct |
| 2 | WO01, WO02 (reactions) | ~2,100 | same; conflicts listed, not hidden |
| 3 | WO05, WO06, WO07 (genes in varieties, QTL, pathotypes) | ~2,900 | same |
| 4 | WO08, WO09 (advisories), WO10 triggers converted by hand | ~3,300 | an advisory with dose has been read by someone who knows the crop |
| 5 | WO11 gap-fill, WO12 cross-tool recheck of a random 200, review-app pass to flip `status` to `reviewed` where checked | ~3,400 | final audit: every quote exact or explained |

Each step ends with a release (`kg load --release`, compare, `kg promote`), so progress is always shippable and reversible.
Time: a research run takes the tool 20-60 minutes; ingest takes minutes; the human sample takes ~30 minutes per 100 claims. Roughly 12 runs, ~6-8 working days
of attention spread over 2-3 weeks, depending on how quickly the first batches reach 95 %.

## 5. Quality gates and the numbers we report

Per batch: accepted / needs_review / unverifiable / rejected counts and the reason table (printed by the ingest report); sample accuracy; the share of rejected
for "quote not found" (a proxy for the model paraphrasing - if > 20 %, rewrite the prompt before the next run).
Per release: claims by type, tier mix, **multi-source share** (today 3 %, target 25 % by step 5), `kg verify-quotes` exact share (target > 90 %), reviewed share, count
of disputed variety/disease pairs.

The sample rule is statistical, not decorative: with a true error rate of 10 %, a 10-claim sample misses it 35 % of the time (0.9^10), so samples are
`max(10, 10 %)` and two errors fail the batch.

## 6. Known gaps in the system that this plan will hit (fix as they appear)

1. **Stale resistance.** Raj 4037 is "resistant" (2004 notification, tier A) and "susceptible" (2020-22 field study); the conflict rule only pairs claims with the *same* stage/place/season.
   Needed: a `disputed` signal across contexts and an age rule for notification-only rust resistance. Do this before step 2 or the reaction layer will mislead.
2. **Zones.** Only MP and MH exist as AgroZones; AICRP zones are needed for national documents (step 0).
3. **Pathotype entity ids** carry the pathogen (`pt:<pathogen>:<designation>`), so pathotype names that are only unique per host need care.
4. **EnvTrigger entities** need numeric conditions mapped to sensor variables; WO10 produces leads and a person builds them.
5. **Review capacity** is the real bottleneck for `reviewed` status; the Streamlit review app needs a "batch from file" view (small job).
6. **Copyright and politeness**: only quotes of <= 700 characters, always with the link; respect robots.txt; no paywall circumvention; no personal data.

## 7. What I need from you

- ChatGPT Deep Research (Plus/Pro) and Grok access for ~12 runs; paste the prompt from `docs/research_prompts/ready/`, save the output blocks to a `.jsonl`.
- ~30 minutes per batch for the spot-check, ideally from someone who has seen the crop (an agronomist reads an advisory dose faster than I can).
- A decision on whether `reviewed` status should require two people for tier A.

How to run: [docs/research_prompts/README.md](research_prompts/README.md).
