# Research needed: environmental triggers, management practices, and a few genes

**Updated 2026-09-26 (third revision)** after three research passes (via three different AI tools
in the last round alone) closed all but 4 of the original 17 diseases on the trigger+advisory
front. This version lists only what's **still actually missing** — don't re-suggest sources
already tried and ruled out below.

**Progress so far**: 14 of 17 diseases now have a real environmental trigger; 14 of 17 have a real
management advisory. Only 4 disease/dimension gaps remain, listed in full below — everything else
in the knowledge base is done on this front.

---

## How to use this file (same standard as before, repeated because it matters)

Every fact in this knowledge base is a claim backed by a **real, checked source**: a PMID or DOI, a
verbatim quote from the paper's own abstract or full text, and a note on whether it's open access.
For each finding, report back:

1. **PMID and/or DOI** — the real identifier, not a guess.
2. **Title, journal, year** — exactly as published.
3. **Open access?** — check via `https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=EXT_ID:<PMID>&format=json`, or `https://api.openalex.org/works/doi:<doi>` (no email/key needed). If both return nothing, that's not disqualifying — say so and give a publisher/journal-archive link instead. This has repeatedly worked: APS back-issues pages, an MDPI page, a Springer OA page, an ICAR ePubs PDF, and a paper's own author-uploaded copy on academia.edu have all been reached directly when the "official" route was paywalled or blocked.
4. **The exact verbatim quote** containing the number(s) or practice — not a paraphrase, and not an AI tool's own summary of the finding. If you can only get a paraphrase (e.g. from a citation-graph tool like Semantic Scholar), say so explicitly and give the paraphrase separately from anything you present as a "quote."
5. **Which specific gap it fills** — and say clearly if it's the paper's **own** experimental/field result versus a citation to a *different* paper. This distinction has mattered repeatedly.

**Do not promote a tested range to a threshold, and do not confuse a growth/yield effect with a
disease-severity effect.** Two real examples from this project's own history:
- A paper testing 20/24/28/32°C and finding infection at all four is evidence the range does *NOT*
  discriminate risk — not evidence for a 20-32°C threshold.
- A paper finding that soil moisture affects plant *stand/root weight/vigor* is not the same as it
  affecting disease *severity* — check which variable the paper's own statistics were run on before
  treating a moisture (or temperature) effect as a disease trigger.

Available sensor variables: air temperature (°C), relative humidity (%), soil temperature (°C),
soil moisture (% VWC), dew point (°C), hours/day with RH ≥ 80% or ≥ 90% (30-day rolling average
supported), rainfall (mm), wind speed (m/s), leaf-wetness-hours proxies.

---

## Wheat

### Powdery mildew (*Blumeria graminis* f. sp. *tritici*) — dis:wheat:powdery_mildew
**Status: has a real env trigger now (26-30°C disease-free ceiling); still missing a management
advisory.** This is the *only* remaining gap for wheat.
**Already tried and ruled out:** the trigger paper itself (Matić et al. 2018, PMID 30140185, open
access) is purely a controlled-environment CO2/temperature study — no management content at all.
An earlier candidate (PMID 30699700) was also checked and has no usable numbers.
**Need:** fungicide timing/efficacy data (percent control, growth-stage timing) or a real cultural
practice (e.g. row spacing, nitrogen management, resistant-variety deployment) with actual
supporting data — a field trial or review, not another modeling/controlled-environment paper.

---

## Chickpea

### Rust (*Uromyces ciceris-arietini*) — dis:chickpea:rust
**Status: has a management advisory now (fungicide efficacy, >77% control); still missing an env
trigger.** This is the *only* remaining gap for chickpea.
**Already tried and ruled out:** the management paper itself (Sabale et al. 2024, DOAJ open access)
is a pure field-efficacy fungicide trial with no environmental/weather data. Two earlier passes
found nothing with real temperature/humidity numbers for this pathogen at all.
**Need:** any real temperature, humidity, or leaf-wetness threshold for infection or spread —
broaden to ICAR technical reports, Indian Journal of Agricultural Sciences, or non-English-language
sources if needed. If genuinely nothing exists in the literature, that is itself a valid, useful
answer for this one (three passes have now come up empty on this specific angle).

---

## Soybean

### Bacterial pustule (*Xanthomonas citri* pv. *glycines*) — dis:soybean:bacterial_pustule
**Status: still completely empty on both trigger and advisory** (has 1 gene, Rxp, and 2
variety-reaction records — nothing else). This is the single thinnest-covered disease remaining in
the whole knowledge base.
**Already tried and ruled out, across three research passes:** general epidemiology and
rain-splash-transmission searches; a lead toward inoculation-condition papers around 28°C/high RH
that were correctly flagged as lab inoculation protocols, not field-risk thresholds; extension
bulletins that all repeat "85-90°F, wet conditions favor disease" with no traceable primary source
behind the number. This is a genuinely thin area of the peer-reviewed literature.
**Need:** any real field-condition (not inoculation-chamber) temperature/humidity/leaf-wetness
threshold tied to natural infection or spread, or any real cultural/chemical practice with
supporting field data. If nothing turns up on a fourth pass, that itself is worth stating plainly —
this disease may simply lack the kind of quantitative literature the rest of the KB has.

### Soybean mosaic virus (SMV) — dis:soybean:mosaic_virus
**Status: still completely empty on trigger and advisory** (has 3 genes now: Rsv1, Rsv3, Rsv4 — the
gene catalogue is done, found across two research passes).
**Already tried and ruled out:** papers on strain transmission genetics and Rsv-gene mapping (useful
for genes, not management); a 2026 aphid-habitat MaxEnt model that names temperature seasonality as
important but gives no usable field threshold.
**Need:** since SMV spreads via aphid vectors (temperature-dependent) and seed transmission rather
than classic weather-triggered infection, useful finds here would be real data on: (a) planting-date
guidance, (b) seed-certification/virus-free-seed practices with measured efficacy, or (c) aphid
flight/activity thresholds (temperature or degree-day based) tied to SMV spread specifically (not
just general aphid biology). A genuinely different kind of finding than the rest of this file —
approach it from the vector-biology angle, not the classic infection-weather angle.

---

## When you find something

Report back with the 5 items listed at the top. Everything gets independently re-verified against
Europe PMC/OpenAlex or the publisher/archive page directly before it goes into the knowledge graph
— that step happens regardless of which tool found the lead.
