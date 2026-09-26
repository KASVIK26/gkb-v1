# Research needed: environmental triggers, management practices, and a few genes

**Purpose of this file**: a self-contained research brief for finding real, citable papers to fill
specific gaps in the AgriHub Genomic Knowledge Base (GKB). Hand this to any AI tool or use it
yourself. It lists exactly what's missing, per disease, and exactly what's already been tried and
ruled out — so you don't duplicate work already done.

## What "done" looks like — read this before searching

Every fact in this knowledge base is a claim backed by a **real, checked source**: a PMID or DOI,
a verbatim quote from the paper's own abstract or full text, and a note on whether it's open
access. Nothing is typed from memory or accepted just because a title sounds relevant — this
project's predecessor failed specifically because of fabricated/unverified facts, so the bar here
is real and non-negotiable.

**For each disease below, what I need back is:**

1. **PMID and/or DOI** — the real identifier, not a guess.
2. **Title, journal, year** — exactly as published.
3. **Open access?** — check via `https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=EXT_ID:<PMID>&format=json` (look for `"isOpenAccess"` and a `"pmcid"`). Full text matters — many abstracts don't contain the actual numbers, only the full text does.
4. **The exact verbatim quote** containing the number(s) or practice — not a paraphrase. Copy the
   sentence(s) directly from the abstract or full text.
5. **Which specific gap it fills** — see the disease sections below.

If you can't find a paper that gives a *real number* (not a vague "warm and humid"), say so
explicitly rather than reporting a paper that doesn't actually contain what's needed. Several
entries below list papers that were already tried and found to have *no usable numbers even in
their full text* — don't re-report those as if they were new finds unless you found something in
them that was missed.

### The two kinds of gap

- **Environmental trigger**: a real, numeric threshold (temperature °C, relative humidity %,
  leaf-wetness/dew hours, soil moisture %, rainfall) tied to infection, sporulation, spread, or
  disease expression. Must be a number from the paper's own data, not a general statement.
- **Management practice**: a specific, actionable recommendation (fungicide + timing, resistant
  cultivar names, cultural practice) with the paper's own reasoning, not "integrated management is
  recommended."

The available sensor variables (what a numeric threshold needs to be expressed in) are: air
temperature (°C), relative humidity (%), soil temperature (°C), soil moisture (% VWC), dew point
(°C), hours/day with RH ≥ 80% or ≥ 90% (30-day rolling average supported), rainfall (mm), wind
speed (m/s). A finding expressed in different units (e.g., leaf wetness duration in hours, or a
qualitative "high/low" without numbers) is still worth reporting — just note it clearly so it can
be mapped later.

---

## Wheat

### Stem rust (*Puccinia graminis* f. sp. *tritici*) — dis:wheat:stem_rust
**Have:** 5 genes (Sr2, Sr31, Sr33, Sr35, Sr50), 31 variety-reaction records. **Missing:** env
trigger, management advisory.
**Already tried:** the one candidate paper (a 2026 *Plant Pathology* review, DOI
10.1111/ppa.70203) isn't indexed in Europe PMC at all (too recent) — its "~10-15°C with
intermittent rain/dew" figure was never independently confirmed and shouldn't be trusted without
reading the actual paper.
**Need:** a primary paper (not another review) with real temperature/humidity/rain thresholds for
stem rust urediniospore germination or infection, and/or DMI-fungicide timing recommendations with
real efficacy data.

### Powdery mildew (*Blumeria graminis* f. sp. *tritici*) — dis:wheat:powdery_mildew
**Have:** 3 genes (Lr34/Pm38, Pm6, Pm37). **Missing:** env trigger, management advisory, variety
reactions (the wheat variety source document never reports powdery mildew reactions at all — a
genuine document gap, not something more searching fixes).
**Already tried:** the one candidate paper (PMID 30699700, *Plant Disease* 2015) is **not open
access** — its abstract only reports model R² (72.4%), no actual temperature/RH numbers. The
"15-21°C, RH>70%" figures previously associated with it were never actually confirmed in this
paper and should be treated as unsourced.
**Need:** an open-access primary paper (or one you can get full text for) with real temperature/RH
thresholds for infection or the 7-10 day latent period, and fungicide timing relative to that
latent period.

### Fusarium head blight (*Fusarium graminearum* / *F. culmorum*) — dis:wheat:fusarium_head_blight
**Have:** 2 genes (Fhb1, Fhb7). **Missing:** env trigger, management advisory, variety reactions.
**Already tried:** the one candidate paper (a 2024 *Plant Pathology* review, DOI 10.1111/ppa.13839)
isn't indexed in Europe PMC at all — its "5-15 day windows pre/post anthesis" and "apply fungicide
at anthesis or within 5 days" figures were never independently confirmed.
**Need:** a primary paper with real temperature/RH/rainfall windows around anthesis (BBCH 59-69)
tied to infection risk, and/or confirmed fungicide-timing efficacy data (a very high-value find —
FHB's anthesis-timing fungicide window is one of the most actionable IoT-alert opportunities in
the whole project).

### Stripe rust (*Puccinia striiformis* f. sp. *tritici*) — dis:wheat:stripe_rust
**Have:** 4 genes, 1 env trigger (a real one: cold/humid CART-model window from PMID 42111728),
2 variety-reaction records. **Missing:** management advisory only.
**Need:** fungicide timing or resistant-variety-deployment guidance specific to stripe rust, ideally
from the same paper family (PMID 42111728, *Frontiers in Plant Science* 2026) or a companion paper.

---

## Soybean

### Rust (*Phakopsora pachyrhizi*) — dis:soybean:rust
**Have:** 3 genes (Rpp1, Rpp2, Rpp3), 1 variety-reaction record. **Missing:** env trigger,
management advisory.
**Already tried:** the original candidate paper (PMID 32716274, *Plant Disease* 2020) is **not
open access**; a fuzzy-logic paper (PMID 35062631, *Sensors* 2022, open access, PMCID PMC8781736)
confirmed the leaf-wetness-proxy methodology (RH ≥ 90% converted to hours — matches this project's
own sensor design) but doesn't give the actual numeric thresholds itself; it cites an uncited/
unindexed reference ("Lotufo et al.") for those. **Finding that specific Lotufo et al. paper (or
any paper with the actual fuzzy-set boundaries) would directly close this gap.**
**Need:** temperature/leaf-wetness-hour thresholds for infection, and/or real fungicide-timing
efficacy data (a real, open-access alternative to PMID 32716274).

### Bacterial pustule (*Xanthomonas citri* pv. *glycines*) — dis:soybean:bacterial_pustule
**Have:** 1 gene (Rxp), 2 variety-reaction records. **Missing:** env trigger, management advisory.
**Already tried:** two different search angles on Europe PMC (general epidemiology + weather/rain
splash) returned no primary paper with real numbers at all — this may be a genuinely thin area of
the literature, but a third search angle or a non-Europe-PMC-indexed source could still turn
something up.
**Need:** any real temperature/humidity/leaf-wetness threshold for infection, or timing/practice
recommendations (avoiding field work on wet foliage, seed treatment, resistant cultivars) with a
real source.

### Soybean mosaic virus (SMV) — dis:soybean:mosaic_virus
**Have:** 2 genes (Rsv1, Rsv4). **Missing:** env trigger, management advisory, variety reactions
(the soybean source documents only mention "Yellow Mosaic Virus," a different virus, correctly
excluded — this is a genuine document gap).
**Already tried:** the original candidate paper (PMID 30780699) is about strain transmission
genetics, not management, and doesn't support the "up to 75% seed transmission" or "no resistant
cultivars exist" claims once checked (real max is 43%). A 2026 aphid-habitat MaxEnt model (PMID
42318120, open access) identifies temperature seasonality as important but gives no usable numeric
threshold.
**Need:** since SMV spreads via aphid vectors (temperature-dependent) and seed transmission (not
classic weather-triggered infection), the most useful find here would be planting-date guidance,
seed-certification/virus-free-seed practices with real efficacy data, or **Rsv3's chromosome
location** (tried 3 times, not found — a real paper naming it directly, e.g. Suh et al.'s original
Rsv3 mapping paper, would also help complete the gene catalogue).

### Anthracnose (*Colletotrichum* spp.) — dis:soybean:anthracnose
**Have:** 1 management advisory (seed treatment + declining fungicide efficacy, verified from full
text). **Missing:** genes/QTL (confirmed genuinely absent from the literature — a dedicated search
found no mapped resistance locus in soybean specifically), env trigger.
**Already tried:** the one candidate review paper (PMID 33609073, open access, PMCID PMC7938629)
was checked in full text — no numeric temperature/duration thresholds anywhere, only "warm and
humid conditions" qualitatively.
**Need:** a primary paper with real temperature/rain-duration thresholds for infection (seed-borne,
so early-season conditions matter most).

### Pod and stem blight / Phomopsis seed decay — dis:soybean:pod_stem_blight
**Have:** 1 management advisory (6 named resistant cultivars, real data), 1 variety-reaction
record. **Missing:** genes/QTL (confirmed absent), env trigger.
**Already tried:** an extension publication (Crop Protection Network) gives one real number — seed
moisture <19% prevents infection — but that's a *seed*-moisture threshold, not something the field
sensors (soil/air only) can measure, so it can't be used as-is.
**Need:** a primary paper with a real field-condition (not seed-moisture) threshold — rainfall or
RH during pod-fill/maturity, tied to incidence.

### Rhizoctonia root rot (*Rhizoctonia solani*) — dis:soybean:rhizoctonia_root_rot
**Have:** 1 management advisory (cultural + chemical, from a real abstract quote). **Missing:**
genes/QTL (confirmed absent — few resistant genotypes exist per the literature itself), env
trigger, variety reactions.
**Already tried:** the one candidate review (DOI 10.1111/ppa.12733, not open access) — abstract
gave no numeric temperature/moisture range at all; the "20-32°C, 25-100% moisture" figures
previously written down were never actually in this paper.
**Need:** a primary paper (ideally open access) with a real temperature/soil-moisture range for
seedling disease severity.

---

## Chickpea

### Fusarium wilt — dis:chickpea:fusarium_wilt
**Have:** 1 gene + 1 QTL, 2 env triggers (real ones, race-specific soil temperature optima), 31
variety-reaction records. **Missing:** management advisory only.
**Already tried:** the main environmental-trigger paper (PMID 18943575) is not open access and its
abstract has no management content — it's purely a temperature-modeling study.
**Need:** soil solarization, sowing-date adjustment, or resistant-cultivar-deployment guidance with
real supporting data (a review or field trial, not another modeling paper).

### Collar rot (*Sclerotium rolfsii*) — dis:chickpea:collar_rot
**Have:** 1 env trigger (real: 80% soil moisture peak incidence), 4 variety-reaction records.
**Missing:** genes/QTL (confirmed absent from the literature), management advisory.
**Already tried:** the trigger's own source paper (PMID 30158943, open access) was checked in full
text for management content — none exists; it's a purely mechanistic gene-expression study.
**Need:** a different paper with real cultural/chemical control recommendations and supporting
data — drainage, organic matter, seedling-stage protection (first ~6 weeks) are documented
elsewhere as plausible levers but need a real citable source.

### Rust (*Uromyces ciceris-arietini*) — dis:chickpea:rust
**Have:** nothing at all — zero genes, triggers, advisories, or variety reactions.
**Already tried:** confirmed via two independent searches that chickpea rust genuinely has very
thin genetics/epidemiology literature compared to the other 16 diseases (it's a minor disease for
this crop) — the best source found, an ICRISAT extension bulletin, has a PDF text layer too
fragmented to extract or confirm any real numbers from.
**Need:** literally anything with real numbers or practices — a peer-reviewed paper specifically on
*Uromyces ciceris-arietini* epidemiology or management, if one exists. This is the single
thinnest-covered disease in the whole KG; even a modest, honest finding here would be valuable.

---

## When you find something

Report back with the 5 items listed at the top (PMID/DOI, title/journal/year, open-access status,
verbatim quote, which gap it fills). I'll independently re-verify each one against Europe PMC (or
the paper directly) before writing it into the knowledge graph — that verification step happens
regardless of which tool found the lead, since this project's whole standard is "checked
independently," not "sounds right."
