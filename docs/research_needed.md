# Research needed: environmental triggers, management practices, and a few genes

**Updated 2026-09-26** after two research passes (via two different AI tools) already closed 5
diseases' trigger+advisory gaps and partially filled several more. This version only lists what's
**still actually missing** — don't re-suggest sources already tried and ruled out below, they're
listed precisely so you don't duplicate that work.

**Progress so far**: 9 of 17 diseases now have a real environmental trigger (up from 0 at the start
of this research thread); 9 of 17 have a real management advisory. **5 diseases are fully done**
on both fronts: wheat leaf rust, chickpea collar rot, chickpea dry root rot, soybean charcoal rot,
soybean frogeye leaf spot — don't search for more on these unless you want to add a *second*,
independent corroborating source (not required).

---

## How to use this file (same standard as before, repeated because it matters)

Every fact in this knowledge base is a claim backed by a **real, checked source**: a PMID or DOI, a
verbatim quote from the paper's own abstract or full text, and a note on whether it's open access.
For each finding, report back:

1. **PMID and/or DOI** — the real identifier, not a guess.
2. **Title, journal, year** — exactly as published.
3. **Open access?** — check via `https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=EXT_ID:<PMID>&format=json`. If Europe PMC returns zero hits (common for old or very recent papers), that's not disqualifying — say so and give a publisher/journal-archive link instead (this has worked twice already: an APS Phytopathology back-issues page and an MDPI article page both had to be reached directly).
4. **The exact verbatim quote** containing the number(s) or practice — not a paraphrase.
5. **Which specific gap it fills** (see below) — and say clearly if it's the paper's **own**
   experimental/field result versus a citation to a *different* paper (this distinction mattered
   twice already: one paper's management timing was its own data, but a nearby sentence about
   infection conditions turned out to cite an unrelated, unreachable 2001 paper).

**Do not promote a tested range to a threshold.** If a paper tested 20/24/28/32°C and found
infection at all four, that's evidence the range does *NOT* discriminate risk — not evidence that
"20-32°C is the threshold." This exact mistake was caught and reversed once already this session.

Available sensor variables: air temperature (°C), relative humidity (%), soil temperature (°C),
soil moisture (% VWC), dew point (°C), hours/day with RH ≥ 80% or ≥ 90% (30-day rolling average
supported), rainfall (mm), wind speed (m/s), leaf-wetness-hours proxies.

---

## Wheat

### Powdery mildew (*Blumeria graminis* f. sp. *tritici*) — dis:wheat:powdery_mildew
**Status: still completely empty** — 3 genes only, zero trigger, zero advisory, zero variety
reactions (the wheat variety source document never mentions this disease at all — a document gap,
not fixable by more paper search).
**Already tried and ruled out:** PMID 30699700 (*Plant Disease* 2015) — not open access, abstract
has no real numbers at all (only model R²=72.4%). This is the *only* candidate paper found so far
for this disease across two research passes — genuinely under-covered.
**Need:** any open-access (or full-text-reachable) primary paper with real temperature/RH
thresholds for infection, or the 7-10 day latent period, or fungicide timing relative to it. This
is the highest-priority remaining wheat gap — completely uncovered after two passes.

### Fusarium head blight — dis:wheat:fusarium_head_blight
**Status: has a management advisory now; still missing an env trigger.**
**Already tried and ruled out:** a 2024 review (DOI 10.1111/ppa.13839) isn't indexed anywhere
checkable. A 2021 *Agronomy* paper (DOI 10.3390/agronomy11081549, confirmed open access) gave real
management data (now in the KG) but its one sentence on infection conditions ("20-30°C, ≥16h
wetness") is a **citation to a 2001 paper** (Rossi, Ravanetti, Pattori, Giosuè, *Journal of Plant
Pathology* 83:189-198, 2001) that could not be found indexed anywhere (Europe PMC: zero hits).
**Need:** track down that 2001 Rossi et al. paper directly (try the *Journal of Plant Pathology*
archive, or search by exact title: "Influence of temperature and humidity on the infection of
wheat spikes by some fungi causing fusarium head blight"), or any other primary paper with real
temperature/RH/rain-duration numbers tied to infection risk around anthesis (BBCH 59-69).

### Stem rust (*Puccinia graminis* f. sp. *tritici*) — dis:wheat:stem_rust
**Status: has a real env trigger now (rain + wetness + temperature onset rule); still missing a
management advisory.**
**Already tried and ruled out:** the one candidate review (DOI 10.1111/ppa.70203) isn't indexed
anywhere checkable.
**Need:** DMI-fungicide timing/efficacy data with real numbers (percent control, application
timing relative to infection), similar in spirit to the FHB fungicide-timing paper already used.

### Stripe rust (*Puccinia striiformis* f. sp. *tritici*) — dis:wheat:stripe_rust
**Status: has a real env trigger (cold/humid CART-model window); still missing a management
advisory.**
**Need:** fungicide timing or resistant-variety-deployment guidance with real efficacy data —
ideally from the same paper family as the existing trigger (PMID 42111728, *Frontiers in Plant
Science* 2026) or a companion paper, but any real primary source works.

---

## Soybean

### Rust (*Phakopsora pachyrhizi*) — dis:soybean:rust
**Status: has 2 real env triggers now (classic 1976 temperature/dew-duration data); still missing a
management advisory.**
**Already tried and ruled out:** PMID 32716274 (*Plant Disease* 2020) is not open access — its
abstract only names model classes, no real management numbers.
**Need:** real fungicide-timing efficacy data (percent control at specific application timings), or
resistant-cultivar deployment guidance with actual supporting data.

### Bacterial pustule (*Xanthomonas citri* pv. *glycines*) — dis:soybean:bacterial_pustule
**Status: still completely empty on trigger/advisory** (has 1 gene, Rxp, and 2 variety-reaction
records).
**Already tried and ruled out:** two different search angles across two research passes (general
epidemiology, weather/rain-splash, and a lead toward inoculation-condition papers around 28°C/high
RH that were correctly flagged as inoculation protocols, not field-risk thresholds) found nothing
usable. This is a genuinely thin area of the literature so far.
**Need:** any real field-condition (not inoculation-chamber) temperature/humidity/leaf-wetness
threshold tied to natural infection or spread, or a real cultural/chemical practice with supporting
data.

### Soybean mosaic virus (SMV) — dis:soybean:mosaic_virus
**Status: still completely empty on trigger/advisory** (has 2 genes: Rsv1, Rsv4).
**Already tried and ruled out:** the original candidate paper is about strain transmission
genetics, not management. A 2026 aphid-habitat MaxEnt model identifies temperature seasonality as
important but gives no usable field threshold.
**Need:** since SMV spreads via aphid vectors (temperature-dependent) and seed transmission rather
than classic weather-triggered infection, useful finds here would be: (a) planting-date guidance or
seed-certification/virus-free-seed practices with real efficacy data, or (b) **Rsv3's chromosome
location** (tried repeatedly across both passes, still not found — a paper directly naming Suh et
al.'s original Rsv3 mapping work, or any paper giving its physical/genetic map position, would also
complete the gene catalogue for this disease).

### Anthracnose (*Colletotrichum* spp.) — dis:soybean:anthracnose
**Status: has a management advisory (seed treatment); still missing an env trigger.** (Genes/QTL
confirmed genuinely absent from the literature for soybean specifically — don't re-search that.)
**Already tried and ruled out:** the one candidate review (PMID 33609073, open access, full text
checked) has no numeric temperature/duration thresholds anywhere, only "warm and humid conditions"
qualitatively.
**Need:** a primary paper with real temperature/rain-duration thresholds for infection — seed-borne
disease, so early-season conditions matter most.

### Pod and stem blight / Phomopsis seed decay — dis:soybean:pod_stem_blight
**Status: has a management advisory (6 named resistant cultivars, real data); still missing an env
trigger.** (Genes/QTL confirmed absent.)
**Already tried and ruled out:** an extension publication gives a real number (seed moisture <19%
prevents infection) but that's *seed*-moisture, not something field sensors (soil/air only) can
measure.
**Need:** a primary paper with a real **field-condition** threshold — rainfall or RH during
pod-fill/maturity, tied to incidence, not seed-internal moisture.

### Rhizoctonia root rot (*Rhizoctonia solani*) — dis:soybean:rhizoctonia_root_rot
**Status: has a management advisory (2 independent sources now); env trigger deliberately NOT
created.** (Genes/QTL confirmed absent — few resistant genotypes exist per the literature itself.)
**Already tried and ruled out — read this carefully before searching more**: a primary study
(Dorrance et al. 2003, PMID 30812954) tested 20/24/28/32°C and found infection at **all four** —
i.e., this is evidence that temperature does NOT discriminate risk in that range, not evidence for
a 20-32°C threshold. Do not re-propose that range. A real, different, discriminating threshold
(if one exists in the literature) is what's needed, not a repeat of this same non-finding.
**Need:** a paper that found temperature or moisture conditions that DO limit or discriminate
Rhizoctonia infection risk (i.e., a paper testing a wider or different range than 20-32°C /
25-100% MHC, where a real limiting boundary shows up).

---

## Chickpea

### Fusarium wilt — dis:chickpea:fusarium_wilt
**Status: has 2 real env triggers (race-specific soil temperature optima); still missing a
management advisory.**
**Already tried and ruled out:** the main trigger paper (PMID 18943575) is not open access and its
abstract has no management content at all — purely a temperature-modeling study.
**Need:** soil solarization, sowing-date adjustment, or resistant-cultivar-deployment guidance with
real supporting data (a field trial or review, not another modeling paper).

### Rust (*Uromyces ciceris-arietini*) — dis:chickpea:rust
**Status: still completely empty — the single thinnest-covered disease in the whole knowledge
base.**
**Already tried and ruled out:** two independent Europe PMC searches found nothing with real
numbers. An ICRISAT extension bulletin (the best source located) has a PDF text layer too
fragmented to extract or confirm any real figures from it.
**Need:** literally anything with real numbers or named practices — a peer-reviewed paper
specifically on *Uromyces ciceris-arietini* epidemiology or management, if one exists at all. Try
broadening to Indian Journal of Agricultural Sciences, ICRISAT technical reports (a cleaner PDF/
HTML version than the one already tried), or non-English-language sources. If genuinely nothing
exists, say so explicitly — an honest "the literature doesn't have this" is a valid, useful answer
for this one.

---

## When you find something

Report back with the 5 items listed at the top. Everything gets independently re-verified against
Europe PMC (or the publisher/archive page directly) before it goes into the knowledge graph —
that step happens regardless of which tool found the lead.
