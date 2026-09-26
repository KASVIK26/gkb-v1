# Research needed: environmental triggers, management practices, and a few genes

**Updated 2026-09-26 (fourth revision)** after four research passes. Only **2 gaps remain** out of
the original 17 diseases: soybean mosaic virus (both dimensions — real sources exist but are
blocked by a KG schema limitation, not by the literature) and chickpea rust's environmental
trigger (genuinely thin literature after four independent passes).

**Progress so far**: 15 of 17 diseases now have a real environmental trigger; 16 of 17 have a real
management advisory.

---

## How to use this file (same standard as before, repeated because it matters)

Every fact in this knowledge base is a claim backed by a **real, checked source**: a PMID or DOI, a
verbatim quote from the paper's own abstract or full text, and a note on whether it's open access.
For each finding, report back:

1. **PMID and/or DOI** — the real identifier, not a guess. If a paper genuinely has neither
   (common for pre-2000s regional/non-English journals), say so explicitly rather than inventing
   one — a fabricated identifier is worse than no identifier.
2. **Title, journal, year** — exactly as published. **Double-check the title actually belongs to
   the DOI you're citing** — a DOI resolving to a real paper does not mean the title, quote, or
   framing you're presenting for it are accurate. This exact mistake happened in the last pass:
   a report cited a real DOI under a fabricated-sounding title that didn't match the paper Europe
   PMC returns for that DOI.
3. **Open access?** — check via `https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=EXT_ID:<PMID>&format=json`, or `https://api.openalex.org/works/doi:<doi>` (no email/key needed). If both return nothing, that's not disqualifying — say so and give a publisher/journal-archive/institutional-repository link instead.
4. **The exact verbatim quote** containing the number(s) or practice — not a paraphrase, and not an AI tool's own summary of the finding.
5. **Which specific gap it fills** — and say clearly if it's the paper's own experimental/field result versus a citation to a different paper.

Available sensor variables: air temperature (°C), relative humidity (%), soil temperature (°C),
soil moisture (% VWC), dew point (°C), hours/day with RH ≥ 80% or ≥ 90% (30-day rolling average
supported), rainfall (mm), wind speed (m/s), leaf-wetness-hours proxies.

---

## Chickpea rust (*Uromyces ciceris-arietini*) — dis:chickpea:rust
**Status: has a management advisory now (fungicide efficacy, >77% control); still missing an env
trigger.** This is the only remaining gap for a crop-disease/dimension pair with genuinely thin
literature — four research passes have now come up empty on a clean primary threshold study.

**Already tried and ruled out, in detail:**
- A candidate "M.Sc. thesis by Mekala Sudheer Kumar, 2024" on Krishikosh (18°C germination
  optimum) **could not be verified** — the item link 404s and the named author returns zero search
  hits anywhere. Do not re-cite this specific thesis without first confirming it actually exists
  at a working link.
- An extension note (Patil & Bhat 2013, *Indian Farming*) states germination occurs at 18°C in tap
  water, but gives no primary citation for that number and it couldn't be traced further back.
- The chickpea rust management paper already in the KG (Sabale et al. 2024) has an unreferenced
  sentence in its Introduction mentioning "30-35°C" — but that paper's own Methods confirm it
  collected zero weather data; the sentence is uncited background text, not this paper's result.

**Two new, unexplored leads surfaced but not yet read:**
- A Krishikosh Ph.D. thesis (real, found via search, not yet opened) whose abstract covers
  "survey, variability of pathogen, aerobiology, screening of genotypes, yield loss estimation and
  integrated disease management" for chickpea rust and soybean rust together — the "aerobiology"
  component may contain real weather-correlation data. Worth locating and reading in full.
- A 2024 paper, "Occurrence and Distribution of Chickpea Rust (*Uromyces ciceris-arietini*) in
  Major Chickpea growing Regions of Andhra Pradesh" (ResearchGate listing found, full text not
  accessed — blocked by ResearchGate's JS wall this session; try Google Scholar or the publisher
  directly).

**Need:** open and read either of the two leads above in full, or any other real temperature/
humidity/leaf-wetness threshold for infection or spread. A genuine "the literature doesn't have
this" after a fifth pass would also be a valid, useful answer.

---

## Soybean mosaic virus (SMV) — dis:soybean:mosaic_virus
**Status: real sources exist for both trigger and advisory, but are currently blocked by a
knowledge-graph schema limitation, not by the literature.** This is different from every other
entry in this file's history — no further research is needed on this disease right now. What's
needed is a **schema decision**, not a search.

**What was found (already verified, sitting in `kg/curated/env_triggers_v1.yaml`'s source
comments, not yet promoted to claims):**
- Shin, D.C. et al. (1979). "Effect of Planting Date on the Infection of Necrotic Soybean SMV."
  *Korean Journal of Crop Science* 24(3):59-66. No DOI (pre-dates this journal's DOI assignment).
  Own 1975-76 field trial, 30 cultivars × 4 planting dates: "SMV-N infection was decreased by
  delaying the planting dates." Verified word-for-word against the journal's own English abstract
  on koreascience.kr.
- Kim, Y.H. et al. (2000). "Seasonal Occurrence of Aphids and Selection of Insecticides for
  Controlling Aphids Transmitting Soybean Mosaic Virus." *Korean Journal of Crop Science*
  45(6):353-355. No DOI. Own field trial: "In early seeding, SMV incidence increased rapidly
  between 20 June and 30 June, suggesting that virus spread was strongly correlated with increased
  colonization of aphids." Also verified word-for-word against the journal's own English abstract.

**The blocker:** this project's `Source` model (`curator/model/claims.py`) requires every
`type: publication` source ID to start with `pmid:` or `doi:` (see `SOURCE_ID_PREFIX` in
`curator/model/enums.py`). Neither 1979 nor 2000-era *Korean Journal of Crop Science* articles
were assigned DOIs, and neither is indexed in PubMed. There is no honest way to cite them under
the current schema without either fabricating an identifier (not acceptable) or extending the
schema.

**What's actually needed here is one of:**
1. A decision to extend `SOURCE_ID_PREFIX` with a new prefix for non-DOI journal articles (e.g. a
   `kci:` prefix for Korea Citation Index articles, since KCI does assign a stable article ID even
   when no DOI exists — would need checking whether these two articles have one), or
2. Confirmation that these two sources are acceptable to cite by URL alone under a different
   `SourceType` (e.g. `official_document`), or
3. A different, DOI/PMID-bearing paper that reports the same or a similar finding, if one exists
   (a fifth research pass could specifically look for a review or later paper that cites these two
   1979/2000 results with its own resolvable identifier).

**One more flag for whoever does the next pass:** a source claimed for this gap in the last round
(DOI 10.1094/PDIS-91-10-1255) turned out to have a fabricated-sounding title attached to it —
Europe PMC's real record for that DOI is "Potential for Integrated Management of Soybean Virus
Disease" (Pedersen et al. 2007), not the title presented. The DOI itself is real and the paper is
plausibly relevant (it studies SMV + soybean aphid interactions), but none of its quotes were used
this pass since the mismatch means the framing can't be trusted without an independent read of the
actual paper — worth doing on a future pass if the schema question above gets resolved first.

---

## When you find something

Report back with the 5 items listed at the top. Everything gets independently re-verified against
Europe PMC/OpenAlex or the publisher/archive page directly before it goes into the knowledge graph
— that step happens regardless of which tool found the lead.
