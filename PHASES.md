# AgriHub Genomic KB — Phases & Status

**Purpose of this file:** one place that says, plainly, what is done, what is in progress, and what is next —
for **this repo only**. Read it, correct anything wrong, and it becomes the thing we both check each session.
`RESEARCH_ROADMAP.md` and `TECH_STACK.md` hold the reasoning; this file holds the status.

**Last updated:** 2026-09-25

---

## 0. The system, and this repo's place in it (corrected)

AgriHub is **four independent products**, each its own deployment:

| # | Product | Hosting | Owns |
|---|---|---|---|
| a | Phenomics model | Lightning AI | Image-based disease classification |
| b | IoT device | **Its own Supabase project** | Sensor readings, device logs, telemetry visualization |
| c | **Genomic Knowledge Base — this repo** | This repo's own Supabase project | Variety, disease and gene/QTL data for Central India; environmental-trigger *definitions* derived from papers/datasets, each stored as a fact with a confidence score |
| d | Mobile app (farmers) + web dashboard (researchers) | Separate codebase | The UI that calls into (a), (b) and (c) as three separate backends — deep data for researchers, simple multilingual alerts and remedies for farmers |

**What follows from this for the GKB specifically:**

- This repo's Supabase project stores **only** GKB data. No sensor readings, no device logs, no farmer accounts —
  those belong to (b) and (d), in their own databases.
- The GKB's job is to **answer questions and hand over knowledge**, not to run anything continuously. It exposes
  an API (and/or direct read access) that (b) and (d) call. It does not call them.
- The confidence-scored-tuple design (`Claim` + `Evidence`, computed confidence, tiers) built in Phase 1 is
  exactly what you described — **confirmed correct, no change needed there.**

### This corrects three earlier design choices

An earlier draft of `TECH_STACK.md` and `docs/interfaces.md` assumed one shared backend for the whole AgriHub
system, with this repo's Supabase project also storing sensor readings (an `ops` schema) and farmer-app data
(`public` schema with Supabase Auth for end users). **That was wrong for what you're building.** Corrected:

| Was assumed | Actually | Status |
|---|---|---|
| `ops` schema here holds sensor readings from `POST /v1/ingest` | IoT has its own Supabase project; nothing sensor-related lands here | Removed from plan (§4 below) |
| `public` schema here holds farmer accounts, fields, alerts (Supabase Auth) | That's product (d)'s data, in its own store | Removed from plan |
| FastAPI here is the ingest endpoint for the IoT device | This repo has no ingest endpoint. If a computed "does condition X favor disease Y" answer is useful to (b) or (d), it's a **stateless** endpoint: they send current readings in the request, GKB returns an answer, nothing is stored here | Needs your confirmation — see §1 |

Both `TECH_STACK.md` and `docs/interfaces.md` now carry a warning banner at the top pointing here. I have **not**
rewritten their body text yet — that's next, once §1 is settled.

---

## 1. Open questions — resolved 2026-09-25

| # | Question | Decision |
|---|---|---|
| Q1 | API-only, or also direct Supabase reads for the dashboard? | Still open, not blocking. Default remains API-only until raised again. |
| Q2 | Should GKB own the weather fetch and offer a stateless risk/trigger-matching endpoint? | **Yes.** GKB accepts `(crop, variety, lat/lon, sowing date, optional live sensor snapshot)`, fetches forecast itself (Open-Meteo), translates it into its own `EnvTrigger` variable names, and returns risk + confidence + cited treatment. Nothing is stored — the endpoint is stateless. See §8 (The query engine). |
| Q3 | Which schema holds the manually-run `db/release_schema.sql`? | Moot for the real pipeline — releases always get a **freshly created** `kg_<release>` schema (TECH_STACK.md ADR-7), never a reused dev schema. Whatever schema you tested in (`kg_dev` or `public`) was just a connectivity/syntax check and can be dropped. |
| Q4 | Is the mobile app + dashboard a separate repo? | **Yes** — confirmed as part of the "four products stay separate" decision (§8). |

## 1a. Architecture decision: split products, combined-but-separated-by-runtime within GKB

Confirmed 2026-09-25. Two different questions, two different answers:

- **The four products (Phenomics / IoT / GKB / App) stay fully separate** — separate repos, separate databases,
  separate deployments. They differ in trust boundary, tech stack, and release cadence.
- **Inside this repo, code stays combined, runtimes stay separate.** One shared `curator/` codebase (models, ID
  rules, risk engine) is imported by three independent running processes: the always-on FastAPI service, the
  on-demand curator pipeline (parsing, LLM extraction), and the internal review tool. They share code because
  they share a data model and duplicating it is exactly how the old project's chromosome/gene errors happened;
  they run separately because they have different uptime, traffic and auth needs. **Do not** publish `curator.*`
  as an installable package for the other three products to import — they consume GKB over HTTP or by reading
  `config/vocab/*.yaml`, never by importing this repo's Python.

Nothing downstream is blocked on Q1 — Phases 2–7 (building the knowledge itself) are the same either way, and
are also where most of the work is.

---

## 2. Status at a glance

| Phase | What it is | Status |
|---|---|---|
| 0 | Cleanup: bad data removed, tests fixed, secrets hooked, docs consolidated | ✅ **Done** |
| 1 | Scope, data model, ID rules, release schema, competency questions | ✅ **Done** |
| 2 | Supabase live setup + versioned build pipeline | ✅ **Done** — five real releases (`kg_2026_10_1` through `_5`) built; `kg_current` atomic switchover live and pointing at `kg_2026_10_5`; `kg/manifest.json` (checksums, git SHA, counts) written on every `kg load`, verified by reading it back |
| 3 | Reference layer: gene catalogues, varieties, zones for Central India | 🟡 **Varieties done for MP+Maharashtra** (110 sourced, loaded as 108 entities + 234 claims — see below). Gene catalogue: 14 wheat genes, 6 soybean genes, 1 chickpea QTL — several diseases per crop still genuinely uncurated (no locus found in the literature, not just "not gotten to yet") |
| 4 | Genomic layer: NLR candidates, QTL anchoring from your 3 genome files | 🟡 **4.1/4.2/4.6 done** (streaming parser, domain-based NLR classification, chromosome stats) for chickpea+soybean; wheat structural data loaded but not NLR-classified (its GFF has no domain annotations at all). **4.3 started**: NCBI BLAST+ installed, 1 gene (Lr34) confidently anchored to its real chromosome/position; 3 more attempted and correctly rejected (see below). **4.4 (marker anchoring) not started** |
| 5 | Literature pipeline v2 (grounded LLM extraction) | 🟡 **Source discovery done** — verified bibliography for all 17 diseases (`config/sources/candidate_papers.yaml`); the grounded-extraction pipeline itself not started |
| 6 | Gold-standard evaluation of the extraction pipeline | ⬜ Not started |
| 7 | Structured trial/germplasm data (AICRP, GRIN) | ⬜ Not started |
| 8 | Environmental trigger library | ⬜ Not started — **scope narrowed**, see §7 |
| 9 | Confidence scoring, conflict detection, QC reports | 🟡 Partially built early (see §3) |
| 10 | API for the other three products | ⬜ Not started — **shape depends on Q1/Q2** |
| 11 | Integration contracts with (a)/(b)/(d) | ⬜ Not started — **reframed**, see §7 |
| 12 | Analytics / research findings (vulnerability index, gene deployment) | ⬜ Not started |
| 13 | Versioned release, FAIR publication, papers | ⬜ Not started |

---

## 3. Done in detail

### Phase 0 — Cleanup (2026-09-25)
- Removed 31 irrelevant papers (wrong subject entirely — sports medicine, psychiatry, etc. under fabricated
  headers) and the chickpea GBFF with zero gene features. `data/` now holds only the 3 real genome annotations,
  2 assembly reports, and 17 verified-relevant papers.
- Archived the old 22-edge seed data and its loaders to `archive/legacy_v1/` — factually wrong in many places
  (impossible chromosomes, wrong crop for a gene, invented confidence labels). Do not load them.
- Fixed the test suite (was failing at collection) and pinned Python 3.12 everywhere.
- `.gitignore` now actually excludes `data/raw/` (1.8 GB was one commit away from landing in git).
- `pre-commit` + `detect-secrets` installed, baseline audited, wired into CI.
- Old planning docs moved to `docs/archive/`.

### Phase 1 — Data model & competency questions (2026-09-25)
- `config/vocab/{diseases,sensors,growth_stages}.yaml` — the 17 in-scope disease IDs (across wheat/soybean/
  chickpea), the AgriNode sensor variable vocabulary, and BBCH-based growth stages for all three crops.
  `tests/test_vocab.py` keeps them consistent.
- `curator/model/` — pydantic models for every entity type, claim type and evidence type. Enforces the rules
  that the old seed data violated: chromosome labels are validated per crop, claims must connect the right kinds
  of things, LLM-sourced facts must carry a verbatim quote.
- `curator/normalize/` — canonical ID rules ("HD 3086" → `var:wheat:HD3086`) and synonym resolution (Lr34 =
  Yr18 = Sr57 = Pm38; "yellow rust" → stripe rust; a bare "rust" is flagged ambiguous, never guessed).
- `db/release_schema.sql` (+ `release_schema_postgis.sql`) — the table/view design: `entity`, `claim`,
  `evidence`, `source`, `ref_gene`, plus one read view per relationship type, all filtered to exclude rejected
  claims and model predictions.
- `db/cq/` — 10 of the 12 competency questions (RESEARCH_ROADMAP.md §1.2) as SQL. Tested end-to-end
  (`tests/test_cq.py`) against a synthetic, obviously-fake toy knowledge graph
  (`tests/kg_toy.py`) in a throwaway PostgreSQL instance.
- `docs/scope.md` — the 17 diseases, and the region: **Malwa (Indore), Madhya Pradesh, primary; Maharashtra,
  secondary.**
- Chickpea growth-stage temperature model decided: Soltani et al. (2006), not a flat base-temperature guess —
  see `config/vocab/growth_stages.yaml` for the citations.
- **101 tests passing** (`pytest tests -q -m "not integration"`).

### Phase 2 — build pipeline done and tested; live Supabase load still to run (2026-09-25)
- `supabase/` scaffolded with the real Supabase CLI (`config.toml`, `migrations/`, `functions/`).
- `supabase/migrations/20260925081644_enable_extensions.sql` — enables `pg_trgm` and `postgis`. You've already
  run this and `db/release_schema.sql` manually against your Supabase project as a connectivity/syntax check
  (Q3 — this doesn't matter for the real pipeline, see §1).
- **`curator/cli.py` — the `agrihub` CLI**: `agrihub kg build` validates every file in `kg/curated/` plus the
  reference entities auto-generated from `config/vocab/diseases.yaml`, and reports what a release would
  contain, with zero database needed. `agrihub kg load --release <tag>` creates a brand-new `kg_<tag>` schema
  and loads it — refuses to overwrite an existing release schema (releases are immutable, TECH_STACK.md ADR-7).
- `curator/graph/kg_files.py` — the loader for hand-curated YAML files (`kg/curated/*.yaml`). Format and
  worked example in `kg/curated/README.md`.
- `curator/graph/vocab_entities.py` — Crop/Disease/Pathogen entities and `DISEASE_CAUSED_BY` claims are
  auto-generated from `config/vocab/diseases.yaml` on every build, never hand-typed. Confirmed the shared
  *Macrophomina phaseolina* pathogen (soybean charcoal rot / chickpea dry root rot) is one entity, not two,
  preserving the cross-crop link `docs/scope.md` calls out.
- **`kg/curated/wheat_seed_genes.yaml` — the first real (non-toy) content**, replacing
  `archive/legacy_v1/seed_data.py`. **10 genes, 12 resistance claims, 1 gene-defeated-by-pathotype claim**, every
  fact checked against Europe PMC before being written — not typed from memory:
  - Sr33 (1DS), Sr35 (3AL) — cloned NLR stem-rust genes (PMIDs 23811228, 23811222)
  - Lr34/Yr18/Sr57/Pm38 (7DS) — the durable ABC-transporter gene, one entity with 3 resistance claims (PMID 19229000)
  - Sr2 (3BS) — durable stem-rust locus (PMID 21573954); deliberately **not** merged with Lr27 as a synonym,
    since the source calls it "a multiple resistance locus," not a proven single cloned gene like Lr34
  - Sr31, Lr26, Yr9 (all 1BL) — the classic 1BL.1RS rye-translocation cluster, three separate linked genes,
    not one (PMID 16283230)
  - Sr50 (1D) — a *different* rye translocation from a different donor (cv. Imperial vs. Petkus), despite the
    superficial similarity to Sr31 (catalogue source, MASWheat/GrainGenes)
  - **Sr31 defeated by Ug99, Uganda, 1999** (PMID 30841334) — a real instance of the "gene effectiveness over
    time" analysis RESEARCH_ROADMAP.md Phase 12 calls for, not a placeholder.
  - Fhb1 (3BS) — cloned FHB resistance gene (PMID 27776114); molecular mechanism noted as actively debated in
    the literature rather than overstated as settled
  - Lr21 (1DS) — cloned NLR leaf-rust gene from *Ae. tauschii* (PMID 12807786)
  **Caught and fixed a chromosome error in my own earlier audit while doing this**: RESEARCH_ROADMAP.md had
  said Sr33 was on 1DL; it's actually 1DS (Periyannan et al. 2013). Fixed there too.
- Tested end-to-end against a throwaway PostgreSQL twice (once per batch): build → load → query the loaded
  facts back out → correct chromosomes, correct resistance types, real quotes stored, the Sr31/Ug99/1999/Uganda
  defeat record queryable exactly as entered. **114 tests passing** (up from 101), including regression tests
  that run the actual production `kg/curated/` content through the release gates, so a future bad edit fails CI
  immediately, and one that checks Sr2 was *not* wrongly merged into a synonym.
- **✅ Loaded into your real Supabase project, 2026-09-25.** `kg_2026_10_1` exists in `aws-0-ap-south-1`
  (Mumbai — matches TECH_STACK.md's recommendation) with 45 entities / 29 claims / 29 evidence rows, verified
  by reading them back: correct chromosomes, correct resistance types, the Sr31/Ug99/1999/Uganda record intact.
  **Q3 resolved**: your earlier manual test landed in `public`, confirmed empty (0 rows in all 4 tables) — drop
  it whenever convenient (`DROP SCHEMA public CASCADE; CREATE SCHEMA public;`, Supabase expects `public` to
  exist). `pg_trgm`/`postgis` confirmed enabled.
- Still open: the build manifest (checksums/versions) and the `kg_current` atomic-switchover mechanism (tasks
  2.5/2.4's pointer-repoint part) — not needed until there's a second release to switch between.

---

## 4. What changes in the plan now that scope is confirmed

| Roadmap item | Before (wrong) | Now |
|---|---|---|
| `ops` schema | Sensor ingest table, written by a `/v1/ingest` endpoint | **Removed.** If GKB needs any internal operational tables at all, they're for its *own* curation workflow (pending extractions awaiting review, pipeline run logs) — that would be a schema named `curation`, not `ops`, and holds no sensor data. Not needed until Phase 5. |
| `public` schema | Farmer accounts, fields, devices, alerts, Supabase Auth for end users | **Removed** — that's product (d)'s data. |
| `functions/api/risk.js` / `/v1/risk` | Reads live sensor data GKB stored | **If built at all** (Q2), becomes stateless: caller supplies current readings in the request; GKB supplies variety susceptibility + trigger match + citations; nothing is persisted here. |
| Supabase Auth, RLS on `public` | For farmer/researcher sign-in | **Not this repo's job**, unless Q1 changes — Auth here would be for restricting the *internal curator review tool* to you, not for end users. |
| `config/vocab/sensors.yaml` | Ingestion schema | **Keeps its purpose but reframed**: it's the shared *vocabulary* — the exact variable names and units that GKB's trigger definitions (`EnvTrigger` conditions) are written in, so that whoever calls the stateless matching endpoint (if built) uses the same names. GKB never stores a reading. |

---

### Data sourcing round — 2026-09-26

- **`docs/genomic_datasets.md`** — surveyed pangenomes, genotyping panels (SoySNP50K, CicerSeq/3,366
  chickpea genomes, T3/Wheat), GRIN-Global, PRGdb, and pathogen genomes across all three crops.
  **Recommendation: don't download any of them now.** The 3 reference annotations already in hand
  cover everything currently planned (Phase 4); these datasets earn their download when Phase 4
  needs variety-level haplotyping, not before — downloading now would repeat the 752 MB
  unused-chickpea-GBFF mistake at a larger scale.
- **`config/sources/candidate_papers.yaml`** — a verified reading list, 18 papers across all 17
  in-scope diseases, each with a real PMID/DOI (checked against Europe PMC or a live publisher
  page, never from memory) and a short note on what it says about environmental conditions and
  management. This directly replaces the failure pattern in the old `scripts/fetch_papers.py`
  (RESEARCH_ROADMAP.md Appendix B) — every identifier here was actually looked up, not typed. It's
  a triage list for Phase 5, not KG claims yet: turning `key_findings` into cited, quote-grounded
  `DISEASE_ENV_TRIGGER`/`DISEASE_MANAGED_BY` claims is still Phase 5 extraction work.
  One dropped candidate is worth knowing about: a second stripe-rust source looked right in search
  results, but its DOI resolved to a different journal on a name check — dropped rather than forced in.
- **Caught and fixed a second real data-integrity bug**: `data/raw/papers/wheat/37225584.txt`
  (kept as "relevant" in Phase 0) had the wrong PMID entirely and a header claiming it was about
  soybean white mold. Its real content is a wheat powdery mildew paper — real PMID **37235018**
  (Mourad et al. 2023). Renamed and header corrected. **Flag for later**: the other 16 files kept in
  Phase 0 were only checked for crop/disease keyword relevance, not this kind of PMID/PMCID identity
  mismatch — a full identity audit of those 16 is still open.
### Variety research — 2026-09-26, two passes

**Pass 1** produced 52 varieties (wheat official-document/CZ only, soybean and chickpea
`multi_source_corroborated`, no Maharashtra coverage, chickpea's DPD source unreachable).

**Pass 2 (same day, on request)** fixed exactly the three gaps flagged as open after pass 1:

- **Retried the unreachable DPD chickpea PDF — solved via the Wayback Machine.** The live
  `dpd.gov.in` server is still flaky from this network (WebFetch failed again), but its archived
  copy (dated 2024-07-01) fetched cleanly via `curl`. That single document covers **both**
  Central-released and State-released chickpea varieties — i.e. both MP and Maharashtra — so it
  answered two of the three open items in one fetch.
- **Chickpea upgraded from `multi_source_corroborated` to `official_document` for all 36
  entries** (verified by counting tiers in the file, not asserted). Exact release years replaced
  several of pass 1's `null`s outright: JG 14 is 2009 (not unconfirmed), Jawahar Chana 6 is 2009,
  RVG 201 is 2011 (pass 1 had guessed 2012), RVG 202 is 2015 (pass 1 had guessed 2012).
- **A genuine conflict surfaced and was kept, not resolved**: the official document itself
  describes RVG 202 as "moderately resistant against wilt and dry root rot," which contradicts an
  independent field study (found separately) reporting it highly susceptible to FOC. Both
  citations are now in the file side by side — a real `cq10`-style conflict, not a data-entry slip.
- **Maharashtra added for all three crops**, from the same document pulls:
  - Wheat: 22 Peninsular Zone varieties, `official_document`, from the *same* AICRP source as the
    Central Zone table. One row's PDF text layout had scrambled variety-name-to-notification
    ordering; the pairing was verified correct via a cross-check (GW 322's notification number is
    identical in both the CZ and PZ tables — internal consistency confirmed, not assumed).
  - Chickpea: 10 Maharashtra varieties, `official_document`, from the DPD document above.
  - Soybean: 11 Maharashtra varieties (MAUS/MACS series, PDKV Akola / ARI Pune) — still
    `single_source`, since no notification-level document was found for soybean at all, for
    either state. Soybean remains the weakest-sourced of the three crops.
- Net result: **110 varieties total** (wheat 50, chickpea 36, soybean 24), with region split now
  explicit in the file's structure (`central_zone`/`peninsular_zone` for wheat,
  `madhya_pradesh_state`/`maharashtra_state` for chickpea, `madhya_pradesh`/`maharashtra` for
  soybean) rather than one undifferentiated list.
- `tests/test_notified_varieties.py` rewritten for the new nested-by-region schema — 14 tests,
  including one that specifically asserts the RVG 202 conflict note is never silently deleted.
- **Still open**: soybean's remaining `null` years (JS 335, NRC 157/136, most of the Maharashtra
  MAUS entries) — no stronger document was found for soybean specifically; confirm "Shakti" and
  "MAUS 81" aren't being double-counted as two varieties.

### Loading the variety research into the KG — 2026-09-26

- **`curator/graph/resistance_text.py`** — every one of the 50 distinct `resistance` phrases in
  `notified_varieties.yaml` reviewed by hand once and mapped to (disease, reaction, stage), using
  **exact-string matching, not a keyword regex**: a phrase not in this table raises
  `UnmappedResistanceText` instead of being guessed at, so a future edit to the source file can't
  silently produce a wrong or missing claim. Explicitly documented what was *excluded* and why —
  most importantly, **soybean's "Yellow Mosaic Virus" mentions are never mapped to
  `dis:soybean:mosaic_virus`**, because YMV (whitefly-borne) and SMV (aphid-borne) are different
  viruses; conflating them would have been exactly the kind of error this project exists to catch.
  Also excluded: out-of-scope diseases (Karnal bunt, Ascochyta blight, BGM, stunt, foot rot, loose
  smut, Alternaria/target leaf spot), pests (girdle beetle, pod borer, nematode, etc.), and
  abiotic traits (drought, lodging, quality). "Tolerant" is mapped to MR, not R — tolerance and
  resistance are different concepts and there's no better bucket in the `Reaction` enum; flagged
  in code rather than papered over.
- **`curator/graph/variety_import.py`** — turns `notified_varieties.yaml` into `Variety` and
  `AgroZone` entities plus `VARIETY_RECOMMENDED_FOR_ZONE` and `VARIETY_REACTION` claims. This is a
  **dynamic** transform wired into `agrihub kg build` (like `vocab_entities.py`), not a static
  hand-copied file — editing the source YAML and rebuilding picks up the change automatically.
  Zone assignment never infers from the breeding institute's location, only from what the source
  document actually says: **JGK 6 was bred at JNKVV Jabalpur (MP) but its official area of
  adoption is NWPZ states only, so it correctly gets zero MP/MH zone claims** — caught a bug of my
  own here during testing (I'd initially forgotten that wheat's Central Zone table needs no
  per-row parsing the way chickpea's mixed-state table does, which silently produced zero wheat
  zone claims until a spot-check caught it).
- **Two real releases now live in your Supabase project**: `kg_2026_10_1` (genes only) and
  `kg_2026_10_2` (genes + 108 varieties + 234 variety claims), verified by querying it back —
  "which MP chickpea varieties are resistant to Fusarium wilt" returns 8 real, correctly-sourced
  varieties. **161 entities, 265 claims, 265 evidence rows, 0 release-gate errors.**
- The RVG 202 conflict from the research pass survived into the loaded data intact and is directly
  queryable with its source quote — confirmed by running the actual query against the live database,
  not just asserted.
- `tests/test_variety_import.py` — 14 tests, including one that would fail if the source file
  gained an unreviewed resistance phrase, and one that specifically re-checks the JGK 6
  institute-vs-zone distinction. **147 tests passing overall.**

## 5. Immediate next actions

1. ~~Run the first real load against your Supabase project.~~ **Done 2026-09-25** — `kg_2026_10_1` is live.
2. ~~Genomic dataset survey + recommendation.~~ **Done 2026-09-26** — `docs/genomic_datasets.md`; defer downloading.
3. ~~Verified paper bibliography, all 17 diseases.~~ **Done 2026-09-26** — `config/sources/candidate_papers.yaml`.
4. ~~MP/Malwa notified variety lists, wheat/soybean/chickpea~~, ~~retry the DPD chickpea PDF~~,
   ~~fill confirmed-null years~~, ~~same pass for Maharashtra~~, ~~turn it into loaded `Variety`
   entities and claims~~. **All done 2026-09-26** — `kg_2026_10_2` is live with 108 varieties.
   ~~Remaining: soybean's still-`null` years; confirm "Shakti"/"MAUS 81" aren't double-counted~~
   **Done 2026-09-26** — found ICAR-IISR Indore's archived national variety list
   (`web.archive.org/web/20220617113918/…/varieties.html`, direct fetch to the live site failed
   the same way `dpd.gov.in` did earlier). Confirmed "Shakti" and "MAUS 81" are one variety (the
   list names it "MAUS 81 (Shakti)") — merged the two duplicate entries into one, so the release
   entity count actually **dropped** by 1 (173 → 172), which is correct. Filled in 6 previously
   `null` years (JS 335→1994, Samrudhi/MAUS 71→2002, MAUS 612→2018, MACS 58→1989, Parbhani
   Sona/MAUS 47→2000, Pratishta/MAUS 61-2→2002), each cross-checked against two independent
   tables on the same source page. NRC 157 and MAUS 725 genuinely don't appear on that list at
   all (checked, not just unlucky) — still `null`, needs a different source. NRC 136 has an
   ambiguous, HTML-extraction-garbled fragment that isn't trustworthy enough to use — still
   `null`. Loaded and promoted live as `kg_2026_10_5`.
5. Rewrite the superseded sections of `TECH_STACK.md` and `docs/interfaces.md` (currently just flagged with
   warning banners) to match the confirmed architecture — still pending, no rush since the banners cover it.
6. ~~Build the `kg_current` atomic-switchover mechanism~~ **Done 2026-09-26** — `curator/graph/promote.py`
   (`ensure_meta_schema`, `promote`, `current_release`, `release_history`), wired into the CLI as
   `agrihub kg promote --release X` / `agrihub kg current [--history]`, 7 tests in `tests/test_promote.py`
   proving the view-swap is atomic (every `kg_current` view repoints in one transaction, verified via
   `information_schema.view_table_usage` rather than trusting `pg_get_viewdef`'s search-path-dependent
   text). `kg_2026_10_2` was promoted live first, then superseded by `kg_2026_10_3` below.
   ~~The build manifest (task 2.5, checksums/versions) is still not started~~ **Done 2026-09-26** —
   `curator/graph/manifest.py` (`build_manifest`, `write_manifest`), wired into `agrihub kg load`
   behind a `--manifest-path` option (so tests never touch the tracked file); writes `kg/manifest.json`
   with per-file SHA-256 checksums for every file that actually feeds the bundle (split from
   `sensors.yaml`, which only constrains validation and never emits content), plus the git HEAD SHA
   and dirty flag and entity/claim/evidence counts. 6 tests in `tests/test_manifest.py`. Retroactively
   generated for the currently-live `kg_2026_10_5`.
7. ~~Continue expanding curated genes (soybean/chickpea genes not started at all yet)~~ **Done 2026-09-26,
   partially** — `kg/curated/soybean_seed_genes.yaml` (6 genes: Rpp1/Rpp2 rust, Rsv1/Rsv4 mosaic virus,
   Rxp bacterial pustule, Rcs3 frogeye leaf spot — each PMID-verified via Europe PMC on 2026-09-26) and
   `kg/curated/chickpea_seed_genes.yaml` (1 QTL: Foc5 resistance region on Ca2, diagnostic-marker
   evidence). Loaded and live as `kg_2026_10_3`. Deliberately left uncurated after a real search found no
   mapped locus: soybean charcoal rot/anthracnose/pod & stem blight/rhizoctonia root rot (diffuse QTL/GWAS
   signal only, no single validated gene), chickpea dry root rot/collar rot/rust (screening studies only,
   no mapped locus at all in the literature as of this search). Turning
8. ~~Turn `config/sources/candidate_papers.yaml`'s findings into cited `DISEASE_ENV_TRIGGER` claims~~
   **Started 2026-09-26, first batch done** — `kg/curated/env_triggers_v1.yaml`, loaded and live as
   `kg_2026_10_4`. **Important finding while doing this**: re-checking each candidate paper's
   `key_findings.environmental` text against its actual freely-available Europe PMC abstract found
   that 3 of them do **not** hold up — the numeric thresholds for wheat powdery mildew, chickpea dry
   root rot, and soybean charcoal rot are not present in those abstracts at all (likely typed from a
   full-text read that isn't accessible now, or general knowledge, and mis-attributed). Flagged
   inline in `candidate_papers.yaml` with an `UNVERIFIED` note on each, original text preserved for
   reference. Only 4 diseases got a real trigger this round — wheat leaf rust, chickpea Fusarium
   wilt (both Foc races), chickpea collar rot, soybean frogeye leaf spot — because those 4 are the
   ones whose abstracts actually contained a quotable number. The other diseases' candidate papers
   need full-text access (institutional login or PMC OA subset) to do properly, not another
   abstract-only pass. Added `rh_ge_80_h` to `config/vocab/sensors.yaml` (mirrors `rh_ge_90_h` at a
   lower cutoff) since the frogeye leaf spot model needed it.
   **Second batch, same day**: found that Europe PMC serves full-text XML for the open-access
   subset (`GET /webservices/rest/{PMCID}/fullTextXML`, after checking `isOpenAccess`/`pmcid` on
   the search API) — not institutional access, just a different endpoint. This unlocked 2 more
   diseases whose abstracts alone were silent: chickpea dry root rot (real soil-moisture contrast
   from the full text, though the original "~35 degC / <=60%" figures still aren't confirmed
   anywhere) and wheat stripe rust (the paper's own CART decision-tree result — Tmin<9.1degC,
   Tdew>=6.2degC, RHm>=94% — replacing the "unverified Moroccan study" citation that was flagged
   from day one). Also checked soybean anthracnose's full text (it's OA too) and confirmed it has
   no numbers at all even there — flagged UNVERIFIED like the other three. Checked and confirmed
   NOT open-access (so genuinely need institutional access, not another automated attempt): wheat
   powdery mildew, soybean charcoal rot, soybean rust, soybean mosaic virus, soybean rhizoctonia
   root rot, soybean bacterial pustule, the second soybean pod & stem blight source. **6 of 17
   diseases now have a real trigger** (up from 4). Loaded and promoted live as `kg_2026_10_6`.
   **Third pass, same day, closing out this thread for now**: checked the 2 remaining
   extension-publication sources directly (no Europe PMC gate — freely hosted pages/PDFs).
   Soybean pod & stem blight's Crop Protection Network page has one real number ("seeds will not
   become infected once moisture is below 19 percent") but it's a *seed*-moisture threshold —
   AgriNode has no grain-moisture sensor, only soil and air, so it's documented in
   `candidate_papers.yaml` but not modelled as an `EnvTrigger`. Chickpea rust's ICRISAT bulletin
   PDF's text layer is too fragmented to locate or confirm its own "~20-25 degC" figure — flagged
   UNVERIFIED like the others rather than trusted. Also confirmed wheat stem rust's and wheat
   FHB's DOIs aren't indexed in Europe PMC at all (too recent), so full-text access for those two
   genuinely needs a different route, not another automated attempt. **This closes out the
   env-trigger research thread for this session at 6 of 17 diseases** — the rest need either
   institutional journal access or sources that just don't exist yet in the literature.
   **Fourth pass, same day**: turned to `DISEASE_MANAGED_BY` claims, reusing sources already
   fetched for the trigger work rather than starting a new reading pass. Confirmed 2 real ones:
   wheat leaf rust's own full text explicitly names prothioconazole as "the first choice among
   all treatments" (1-2 sprays at its own stem-elongation/booting/heading timings — not converted
   to standard Zadoks codes since the paper's own decimal notation doesn't obviously map to them),
   and soybean frogeye leaf spot's abstract confirms fungicide-stewardship framing (avoid QoI
   overreliance) as the paper's own point. Checked and found genuinely empty on management:
   chickpea collar rot's full text (purely mechanistic, no recommendations of any kind despite
   naming a more-resistant cultivar) and chickpea Fusarium wilt (paper is paywalled, but its own
   abstract is purely a temperature model with no management content — flagged as "not checked
   against full text" rather than "disproven," since that's a different, weaker claim than the
   others). Also caught and flagged 2 more unverified figures found in passing: collar rot's
   "25-30 degC" (the 80% soil-moisture figure next to it is real; the temperature figure isn't)
   and frogeye leaf spot's more specific mechanism/cultivar/timing claims (the QoI-resistance
   framing itself is real; the specifics around it aren't). 2 of 17 diseases now have a real
   management claim.
9. Expanded `kg/curated/wheat_seed_genes.yaml` with 4 more verified genes (2026-09-26), giving
   wheat its first dedicated stripe-rust and powdery-mildew genes beyond the Lr34-synonym cluster:
   **Yr6NLR1 + Yr6NLR2** (7BL, stripe rust) — a genuine two-gene NLR pair, both required together
   (neither single mutant is resistant; crossing complementary mutants restores it; VIGS-silencing
   either one increases susceptibility) — modelled as two separate Gene entities since that's what
   they are, not a naming quirk. **Pm6/Pm52** (2BL, powdery mildew, from *T. timopheevii*,
   transgenic-complementation validated). **Pm37** (7AL, powdery mildew + narrow-spectrum leaf
   rust to race THDS only, from *T. monococcum*) — a *different allele* of the stem-rust locus
   Sr22 (94.22% identity, "distinct functional divergence" per the source), not a synonym of it;
   documented in a comment since there's no `ALLELE_OF` claim type to represent that relationship
   properly. All 4 verified via Europe PMC full-text XML (open access), same rigor as the original
   10. Gene catalogue is now 14 wheat / 6 soybean / 1 chickpea QTL. Loaded and promoted live as
   `kg_2026_10_8`.
10. Exhaustively re-checked soybean's 4 remaining gene-less diseases (charcoal rot, anthracnose,
   pod & stem blight, rhizoctonia root rot) via full-text/dedicated searches — all 4 confirmed
   genuinely gapped in the literature, not just under-searched (e.g. the one charcoal-rot GWAS
   paper explicitly reports 23 candidate genes across 6 loci with no leading candidate, "no
   explicit ranking or mechanistic validation of any individual gene"). Then found and added
   **gene:chickpea:Ca_14301** — the well-known chickpea "foc1-foc4 cluster" on CaLG02
   (pseudomolecule Ca2), a multi-race Fusarium wilt resistance region, modelled as
   `resistance_type: quantitative` per the source's own transgressive-segregation evidence rather
   than treated as a clean monogenic gene. This is the same locus marker-assisted-backcrossed into
   **Super Annigeri-1** (a variety already in `notified_varieties.yaml`) — a genuine
   cross-reference, but deliberately NOT encoded as a `VARIETY_CARRIES_GENE` claim in
   `kg/curated/`, since `tests/test_kg_files.py`'s `_production_bundle()` tests that layer in
   isolation from `variety_bundle()` by design; documented in a comment instead, with a note that
   it belongs in `variety_import.py` if it's ever formalised as a claim. Chickpea gene catalogue is
   now 1 QTL + 1 gene. Loaded and promoted live as `kg_2026_10_9`.
11. Added **Fhb7** to wheat's FHB gene coverage (previously only Fhb1) — the well-known,
   Science-2020-cloned glutathione S-transferase from *Thinopyrum elongatum* that detoxifies
   trichothecenes. Its native locus (7EL, a Thinopyrum chromosome) doesn't fit our wheat-only
   chromosome validation, so `chromosome` records the wheat arm it's introgressed onto in the
   specific resistant genotype cited (7D), same convention already used for the rye-donor
   Sr31/Lr26/Yr9 cluster. Deliberately documented a real complication found while verifying it,
   rather than presenting a clean story: a follow-up paper (PMID 36015378) found wheat-Thinopyrum
   lines carrying near-identical (>=94%) Fhb7 homologs with **opposite** FHB outcomes — one highly
   resistant, two others "highly susceptible... with nearly whole spike bleached" — so
   `resistance_type: quantitative, spectrum: "genotype-context-dependent"` rather than a universal
   drop-in claim. Wheat gene catalogue is now 15. Loaded and promoted live as `kg_2026_10_10`.
12. Added **Rpp3** to soybean rust (previously only Rpp1/Rpp2, out of the 8 known Rpp1-Rpp7 +
   Rpp6907 loci) — same evidentiary pattern as Rpp2: fine-mapped to a 371-kb interval on Gm06
   containing 5 candidate NBS-LRR genes (Rpp3C), co-silenced together (not narrowed to one, not
   transgenically complemented) — `cloned: false`. Rpp4/Rpp5 were searched but didn't turn up a
   comparably documented paper in this pass; not pursued further to avoid scope creep in a single
   sitting. Soybean gene catalogue is now 7. Loaded and promoted live as `kg_2026_10_11`.
13. Reused 2 papers already fetched in full text for the trigger work to add 2 more
   `DISEASE_MANAGED_BY` claims rather than starting new searches: chickpea dry root rot's own
   Introduction confirms agronomic management (sowing time/location, soil amendments, irrigation
   scheduling) is a real recommendation; soybean anthracnose's full-text Disease Management
   section confirms both seed-treatment fungicides and declining fungicide efficacy, but explicitly
   does NOT mention phosphite-based treatments — flagged that specific figure as unconfirmed in
   `candidate_papers.yaml` rather than carried into the claim. 4 of 17 diseases now have a real
   management claim (up from 2). Loaded and promoted live as `kg_2026_10_12`.
14. Swept the remaining unprocessed `candidate_papers.yaml` entries for accuracy and found the
   most serious issue yet: soybean rust's management claim ("rain-based thresholds outperform
   calendar-based spraying in both efficacy and cost") isn't just unverified — the paper's own
   abstract **contradicts** it, stating "the economic analysis showed no significant differences
   in the risk of not offsetting the costs of fungicide sprays regardless of the system." Flagged
   as CONTRADICTED (a stronger, more specific flag than UNVERIFIED) rather than lumped in with the
   others. Also found soybean rhizoctonia root rot's environmental figures aren't in its abstract
   (flagged UNVERIFIED), but its management framing partially is — added a 5th
   `DISEASE_MANAGED_BY` claim from that real quote. Caught and immediately fixed my own mistake
   mid-edit: briefly wrote a fabricated PMID for the rhizoctonia paper (it genuinely has none, only
   a DOI, confirmed earlier in this same file) before catching it and switching to a `doi:` source
   ID instead — a reminder that this failure mode is easy to slip into even while doing the
   verification work meant to prevent it, not just something that happens when skipping steps.
   5 of 17 diseases now have a management claim. Loaded and promoted live as `kg_2026_10_13`.
15. Finished the audit sweep. Soybean mosaic virus's environmental claim had a second real
   contradiction: the source paper reports seed transmission "ranged from 0 to 43%," not the
   "up to 75%" figure that had been written — flagged CONTRADICTED; its management claim
   (virus-free seed, avoiding late planting, no resistant cultivars) doesn't appear anywhere in
   that paper at all (it's purely transmission genetics), flagged UNVERIFIED with a note that a
   different source is needed. Separately, re-checked the Phomopsis-seed-decay cultivar paper
   (soybean pod & stem blight) that had an unconfirmed PMID from the original research pass —
   found and confirmed PMID 30677383 this time. Its environmental claim (late-season rainfall
   driving incidence) isn't in the abstract, but it has real, strong management data: 6 named
   cultivars (Morsoy R2 491, Progeny 5650/5706, Asgrow 5606/5831, Dyna-Gro33C59) with
   significantly lower Phomopsis seed infection than susceptible checks — added as a 6th
   `DISEASE_MANAGED_BY` claim, the first `varietal`-type advisory in the KG. This closes out the
   candidate_papers.yaml accuracy audit for this session: every entry has now been checked at
   least once against its real source (abstract or full text), not just trusted as originally
   written. 6 of 17 diseases now have a management claim. Loaded and promoted live as
   `kg_2026_10_14`.
16. **Audit correction pass**: double-checked the "every entry checked" claim above and found it
   wasn't quite true yet -- 6 fields across 4 diseases had never actually been flagged, some
   silently correct (no action needed) but several genuinely wrong. Found: wheat leaf rust's
   environmental figure was flat-out superseded (the real, used figure is different field-
   correlation data, and the never-corrected old figure was still sitting there unflagged) and its
   "protecting the flag leaf" management detail was never confirmed; wheat powdery mildew's
   management claim was never checked (paper not open access); soybean charcoal rot's management
   claim doesn't just lack confirmation -- the abstract argues close to the opposite emphasis
   ("agronomic practices... should not be dismissed" vs. the original "resistant cultivars are the
   most promising lever"). Also added explicit "NOT INDEPENDENTLY CHECKED" flags to wheat stem
   rust, wheat FHB, and soybean bacterial pustule's remaining fields -- these 3 sources return zero
   hits on Europe PMC at all, a genuinely different, weaker state than "checked and found
   wanting." No KG content changed in this pass (`kg_current` still `kg_2026_10_14`) -- pure
   documentation accuracy.
17. **Rebuilt the demo dashboard** (`public/` + `functions/`) against Supabase — it was the v1
   Cloudflare Pages demo, querying Neo4j, dead since that database was deleted. New
   `public.kg_*` bridge views (`supabase/migrations/20260926120000_dashboard_views.sql`) sit on
   top of `kg_current` and stay correct across every future promotion. Added the actual new
   capability: `functions/api/triggers.js` takes a crop, optional variety, and sensor readings,
   and reports which `DISEASE_ENV_TRIGGER` claims fire, with the matched disease's advisory and
   the variety's own documented reaction if known — a real, if single-snapshot-simplified, first
   exercise of the trigger/advisory data (not the real windowed risk engine, Phase 11, not built).
   Tested end-to-end locally via `wrangler pages dev` against the live database across all three
   crops. See `public/README.md`.
18. **Started Phase 4 (genomic layer)**, tasks 4.1/4.2/4.6: rewrote the GFF3 parser as a genuine
   streaming generator (`curator/genome/refgenes.py`, new module — deliberately not touching
   `curator/parsers/`, which is Neo4j-era code under review for removal in a separate pass) that
   preserves `Dbxref`/`Note`/`ancestorIdentifier`, and added NLR/RLK classification using
   InterPro domain accessions individually verified against the InterPro API (not typed from
   memory): NB-ARC (IPR002182) for the core NLR call, TIR (IPR000157) → TNL, RPW8 (IPR008808) →
   RNL, kinase (IPR000719) + LRR family domains → RLK. Ran against the real genome files in
   `data/raw/`: chickpea 318/30,257 genes flagged NLR/RLK (1.1%), soybean 807/48,387 (1.7%,
   plausibly higher than chickpea given soybean's known extra whole-genome duplication), wheat
   0/136,408 — wheat's NCBI RefSeq GFF carries no domain annotations at all (only free-text
   `description`), so it's loaded with structural data only rather than guessed from a keyword
   match on that text (a real test — `test_wheat_has_no_domain_data_so_is_never_flagged` — locks
   this in). Runs in ~9s for all 3 crops combined (AC was "<5 min for wheat alone"). Loaded into
   `kg_2026_10_14`'s `ref_gene` table (215,046 rows) via a new, independent `agrihub genome
   build-refgenes` / `agrihub genome load-refgenes` CLI pair — deliberately not folded into
   `kg load`, since reference-genome data doesn't change with each curated-content release.
   **A genuine cross-check passed**: soybean's Gm18 is the single most NLR-dense chromosome in
   the real genome (84 flagged genes) — and that's exactly the chromosome our independently
   literature-sourced `gene:soybean:Rpp1` (rust resistance) sits on.
   **Not done at the time**: tasks 4.3/4.4 needed BLAST/DIAMOND, not installed — flagged rather
   than faked with a weaker substitute.
19. **User approved installing BLAST+; did task 4.3 (cloned-gene anchoring)**. Installed NCBI
   BLAST+ 2.17.0 (official ftp.ncbi.nlm.nih.gov build, ~143MB, extracted to `.tools/`, gitignored
   — a portable/no-admin install, not added to system PATH). Found and downloaded the 3 real
   reference proteomes needed to BLAST against (chickpea + soybean from the same LegumeInfo
   DataStore the GFF3s came from; wheat from NCBI's own FTP for the same GCF assembly) — these
   didn't exist locally before, `data/raw/` only had GFF3s and assembly reports.
   For query sequences, fetched real published protein sequences (NCBI/UniProt, each cross-checked
   against its cloning paper's author list or gene-name field before use) for the 4 wheat genes
   that have one at all among our 11 `cloned: true` entries: Sr33, Sr35, Lr34, Lr21. Ran BLASTP
   against the IWGSC CS RefSeq v2.1 proteome.
   **Result: only Lr34 anchored with confidence** — chromosome 7D, 48,949,410-48,961,453
   (97.4% identity, matches the literature exactly). Sr33 and Sr35 are donor-species introgressions
   (Aegilops tauschii, Triticum monococcum) that the Chinese Spring reference never carried in the
   first place, so their ~87-90%-identity best hits are the closest native paralogs, not a real
   anchor -- no claim written. Lr21's best hit was only 63.6% identity, too divergent to call.
   **A serious near-miss, caught and documented rather than silently avoided**: Lr34's single
   highest-scoring BLAST hit (100% identity) sits on chromosome **4A** -- directly contradicting
   the well-established literature chromosome (7DS, Krattinger et al. 2009, already cited in this
   file). Cross-checking every hit's chromosome against the literature (not just taking rank order)
   found the real anchor at ~97% identity on 7D instead; the 4A hit is a same-family ABC-transporter
   paralog. Taking "best BLAST hit" at face value would have anchored Lr34 to the wrong chromosome
   -- the exact class of error this whole project was rebuilt to stop making. Documented as a
   standing methodology note in `kg/curated/wheat_seed_genes.yaml` for whoever does this at scale.
   Also caught and fixed a real ID-consistency bug while wiring this up: the curated `RefGene`
   entity used `locus_id: LOC123169079`, but the bulk `ref_gene` table (loaded by
   `curator/genome/refgenes.py`) actually stores wheat IDs as `gene-LOC123169079` (its raw GFF ID
   has no colon to strip a prefix from, unlike chickpea/soybean) -- the two didn't join until
   fixed. Loaded and promoted live as `kg_2026_10_16` (188 entities, 293 claims), verified the
   anchor resolves correctly by joining `v_gene_located_at` all the way through to the real
   chromosome/coordinates. Task 4.4 (marker sequence anchoring) is still not started.
20. **Closed wheat's NLR-classification gap** (flagged in item 18) using a real external dataset,
   at the user's direction. The user found the right URGI (IWGSC) download pages and asked which
   file was needed; fetched `iwgsc_refseqv2.1_functional_annotation.zip` directly (URGI is
   reachable from this environment, no relay needed) — real InterPro/Pfam/GO annotation per wheat
   gene, keyed by IWGSC's own `TraesCS...` gene IDs. Those IDs don't match NCBI's `LOC...` IDs
   already loaded (checked: the official ID-correspondence file only cross-references IWGSC's own
   annotation versions against each other, never against NCBI) — so also downloaded IWGSC's own
   gene-coordinate GFF3 (415MB) and built a coordinate-overlap join instead
   (`curator/genome/wheat_domains.py`), verified first on a gene both annotations independently
   place at the same position give or take a few bp. Genes with an ambiguous (0 or 2+) overlapping
   IWGSC gene are deliberately left unclassified rather than guessed at — a real test locks this
   in. **Result: 2,184 of 136,408 wheat genes now flagged NLR/RLK (1.60%)** — TNL=6, RNL=3, NL=1334,
   RLK=841 — closely in line with soybean's 1.7% and chickpea's 1.1% from the same classifier.
   Reloaded into `kg_2026_10_16`'s `ref_gene` table, replacing the old all-`is_nlr=false` wheat
   rows. Wheat's genomic layer (4.1/4.2) is now on equal footing with soybean/chickpea's.
21. **Resumed targeted literature research on soybean's remaining gaps**, per the user's choice
   (manual research passes now, not Phase 5 yet). A second search specifically for a primary
   paper with real numbers (rather than trusting the one review already in
   `candidate_papers.yaml`, which had none) found one for charcoal rot: an open-access 2026 Plant
   Pathology Journal paper with a genuinely quotable result — disease incidence "reaching 92.4%
   and 100%" at 35 degC soil temperature vs. weaker pathogenicity at 25 degC. Added
   `env:soybean:charcoal_rot_high_temp` (soil_temp_c >= 35, mean/24h) and an irrigation-management
   advisory. The same paper's moisture-stress finding was reported as watering *frequency* ("once
   per day" vs "once every three days"), not a soil-moisture percentage — deliberately not forced
   into a numeric `EnvTrigger` condition it doesn't actually support; used qualitatively in the
   advisory instead. 7 of 17 diseases now have an env trigger, 7 of 17 have a management claim.
   Loaded and promoted live as `kg_2026_10_17`.
22. **Continued the research pass; confirmed several more genuine gaps rather than forcing weak
   data.** Env triggers: soybean bacterial pustule (2 different search angles, zero primary papers
   with real numbers at all — genuinely thin literature) and soybean mosaic virus (aphid-vector
   temperature data exists at the species-distribution-model level, e.g. a 2026 MaxEnt habitat-
   suitability paper, but nothing at the field-trigger level) stay uncovered. Soybean rust's env
   trigger led to a fuzzy-logic paper (PMID 35062631, OA) that confirmed our own `rh_ge_90_h`
   sensor-vocab design matches real published methodology ("leaf wetness determined by...RH >= 90%,
   converted into hours") but doesn't itself give the numeric thresholds — it cites a different,
   unindexed paper for those. Rsv3 (soybean SMV) still has no confirmed chromosome after a third
   search attempt.
   **Checked something more useful than another paper search**: re-examined the *already-sourced*
   variety documents directly for the diseases with zero `VARIETY_REACTION` claims (wheat powdery
   mildew/FHB, soybean frogeye leaf spot/mosaic virus/rhizoctonia/anthracnose). Confirmed these are
   genuine **source-document gaps**, not mapping bugs: the wheat AICRP PDF never mentions powdery
   mildew or FHB for any variety (only rust and Karnal bunt); the soybean sources only ever mention
   "Yellow Mosaic Virus" (correctly excluded from SMV per `resistance_text.py`'s documented rule —
   verified this exclusion is firing correctly, not swallowing real SMV data) and never mention
   frogeye/rhizoctonia/anthracnose at all. Closing these needs a richer soybean variety-notification
   document (if one exists — unlike wheat/chickpea, no AICRP-style official soybean release PDF was
   found in the original variety research pass) or germplasm screening-trial data (Phase 7), not
   more searching of what's already in hand.
23. **Wrote `docs/research_needed.md`** at the user's request — a self-contained brief for the 10
   diseases still missing an env trigger or advisory, listing exactly what's missing and what's
   already been tried per disease, meant to be handed to other AI tools. **The user ran it through
   another AI tool and returned a research report**; every claim in it was independently
   re-verified against Europe PMC before use (per the brief's own stated rule), not trusted at
   face value. Two genuinely new, real findings survived verification:
   - **Chickpea collar rot finally has a management advisory** (previously the whole disease had
     zero: `dis:chickpea:collar_rot` had a trigger but nothing else) — Hameeda et al. 2010,
     confirmed via abstract: "Disease incidence was reduced up to 47%" with *Pseudomonas* sp.
     CDB35 or captan seed treatment. The other tool's report included a detailed per-treatment
     table (83%/80%/67%/47%/53%/47%) that would need full-text access to verify — Europe PMC
     flags this paper as NOT open access despite having a PMCID, and `fullTextXML` returned a
     server error, so that table was deliberately **not** carried into the KG at that granularity;
     only the single abstract-level figure is used.
   - **Soybean rhizoctonia root rot's management advisory gained a second, independent
     citation** (Dorrance et al. 2003, verified) — but its real value was a correction, not an
     addition: this paper tested 20/24/28/32°C and found infection at *all four*, i.e. "the
     temperatures evaluated in this study were not limiting to the isolates tested." That's very
     likely the actual origin of the "20-32°C" figure that had been sitting in
     `candidate_papers.yaml` flagged UNVERIFIED against a *different* paper — so the number
     probably wasn't fabricated, just misattributed. More importantly, its meaning is the opposite
     of a threshold: it's evidence that temperature does *not* discriminate risk in that range, so
     no `EnvTrigger` was created from it. Documented explicitly in both files so this isn't
     mis-encoded as a min/max condition later.
   The other tool's report also correctly declined to promote two "LEAD-ONLY" items (soybean
   bacterial pustule inoculation conditions, a secondary-source soybean rust leaf-wetness figure)
   to verified claims — that discipline was correct and nothing further was done with those here
   either. Loaded and promoted live as `kg_2026_10_18`. 8 of 17 diseases now have a management
   claim (up from 7); the env-trigger count is unchanged at 7/17.
24. **Second research pass via a different AI tool (Grok), same `docs/research_needed.md` brief —
   the strongest batch yet.** All 3 concrete findings independently re-verified before use (2
   against Europe PMC, 1 — too old to be indexed there — directly against the American
   Phytopathological Society's own back-issues archive, reached via the browser pane after
   `WebFetch` got a 403). All 3 fill diseases that had **zero** env trigger or advisory before this:
   - **Wheat stem rust finally has an env trigger**: a field-validated mechanistic model
     (Salotti, Bove & Rossi 2022, open access) with a precise Onset rule — rain >=1mm/h, followed
     by a >=3h wetness period, with mean temperature 15-32°C during that period. Modelled as 3
     independent conditions (our `EnvTrigger` schema can't express "temperature specifically
     during the detected wetness window" as a compound rule) — documented as an approximation.
   - **Wheat FHB finally has a management advisory**: real field-trial data (González-Domínguez
     et al. 2021, MDPI, open access, not indexed in Europe PMC at all — confirmed by loading the
     page directly in the browser instead) — fungicide efficacy was >90% for FHB incidence when
     applied 1-4 days *before* infection, dropping to 58% at 5 days *after*. This is the paper's
     own primary 2-year field result, not a citation. A second sentence in the same paper
     ("infection occurs... at 20-30°C with >=16h wetness") is *not* this paper's own finding —
     it cites a 2001 paper that isn't indexed anywhere I could check, so it's recorded as a lead,
     not a claim.
   - **Soybean rust finally has an env trigger**: a classic 1976 primary paper (Marchetti,
     Melching & Bromfield) — germination 10-28.5°C, no infection above 27.5°C, and two distinct
     favourable infection bands (20-25°C with >=6h dew; 15-17.5°C with >=8h dew). Modelled as two
     separate `EnvTrigger` entities matching the paper's own two-band structure, not one merged
     range. **Likely explains an old mystery**: this paper's real numbers are probably the actual
     origin of the "10-27.5°C / >=6h" figures previously flagged UNVERIFIED against a *different*,
     2020 paper — the same "misattributed, not fabricated" pattern already seen once with the
     soybean rhizoctonia figures.
   9 of 17 diseases now have an env trigger (up from 7); 9 of 17 have a management claim (up from
   8). Loaded and promoted live as `kg_2026_10_19`.
25. **Third research pass, 3 independent AI reports against an updated `docs/research_needed.md`
   — by far the largest single haul, 11 genuine findings.** Every claim independently re-verified
   before writing anything (Europe PMC, OpenAlex/Semantic Scholar metadata, direct publisher/OA
   mirrors, or a downloaded full-text PDF read start-to-finish) — never trusted from a report's own
   quote alone. Two of the three reports independently converged on the same Fusarium head blight
   and soybean rust sources, a strong corroboration signal; one report's own "verified" Rhizoctonia
   moisture claim (misreading Dorrance 2003's stand/vigor data as a disease-severity finding) was
   caught and not used — its abstract explicitly says "no significant main effect on disease
   severity" for that moisture arm.
   - **Wheat FHB finally has an env trigger**: tracked down the actual Rossi et al. 2001 paper
     (the one the 2021 Agronomy paper's "20-30°C, >=16h" sentence had cited but didn't itself
     report) via academia.edu, uploaded by the author himself. Own controlled-environment data:
     F. graminearum infection-frequency optimum 28.0-29.0°C (detached-spike inoculation,
     10.0-35.0°C tested range).
   - **Wheat powdery mildew has its first-ever content of any kind**: a real, discriminating
     temperature ceiling — 0.00 disease index at 26-30°C regardless of CO2, vs. 37-79 at 18-26°C
     (Matić et al. 2018, open access, PMC6097819; confirmed via Europe PMC's fullTextXML endpoint).
     Correctly distinguished the paper's own data from its citation of Manners & Hossain 1963.
   - **Wheat stem rust and stripe rust now have management advisories**: Schmitt et al. 2026 (open
     access, Journal of Crop Health) for stem rust — curative DMI+strobilurin/carboxamide mixtures
     1-5 days post-inoculation; Basandrai et al. 2020 (open access, ICAR) for stripe rust —
     tebuconazole gave 99.64% disease control across 2 seasons. Both full PDFs downloaded and read.
   - **Soybean rust now has a management advisory**: Mueller et al. 2009 — a genuinely public-domain
     APS article (confirmed by the PDF's own copyright line, despite Plant Disease defaulting to
     subscription access) with real multi-country field yield data: 16-114% yield gain over
     untreated, growth-stage timing (R1 vs. R3/R5) depending on when rust was first detected.
   - **Soybean anthracnose finally has an env trigger**: tracked an external report's bare
     KoreaScience article ID down to its real DOI, authors, and bilingual abstract directly on
     koreascience.or.kr — >=8h wetness at 30°C required for C. truncatum lesion development.
   - **Soybean pod & stem blight finally has a field-condition env trigger**: Shortt et al. 1981
     (APS back-issues archive, full PDF) — a 3-year, >8,000-seedlot Illinois study found rainfall
     during pod fill (not temperature or geography) was the dominant factor (r²=0.75).
   - **Soybean Rhizoctonia root rot finally has a real, discriminating env trigger** — the gap this
     project explicitly flagged as unresolved twice before: Balbinotti et al. 2026 (open access,
     Phytopathologia Mediterranea, full PDF read including supplementary tables) directly measured
     RRR *severity* (not just stand/yield, unlike Dorrance 2003) against soil moisture across 2
     greenhouse experiments and 5 soil types — severity fell linearly (R²mostly >0.70) as moisture
     rose from 50% to 95% WHC. This does not contradict Dorrance's temperature non-finding, which
     stands unchanged; it's a different variable, a different (and more direct) measurement, and a
     genuinely different, newer, larger study.
   - **Chickpea Fusarium wilt and chickpea rust now have management advisories**: Elbouazaoui et
     al. 2022 (MDPI, open access) — early (mid-December) sowing significantly reduced all three
     wilt-severity parameters vs. late (mid-February) sowing, in a 2-season Morocco field trial.
     Sabale et al. 2024 (DOAJ, open access) — two sprays of azoxystrobin+difenoconazole cut rust
     severity >77% with a 2.32 cost:benefit ratio — chickpea rust goes from the single thinnest
     disease in the KB to having real management content.
   - **Soybean mosaic virus's Rsv3 gene finally has a chromosome**: found by name per this
     project's own repeated, explicit ask. Suh et al. 2011 (Gold OA, confirmed via 5 independent
     mirrors of the exact abstract text) mapped Rsv3 to a 154-kbp interval on chromosome 14
     (linkage group B2) containing a CC-NB-LRR gene cluster — added as `gene:soybean:Rsv3`,
     `cloned: false` (locus/cluster, not a single complemented gene). A follow-on paper narrowing
     this to one candidate gene (Glyma14g38533) was left as an unconfirmed lead, not curated.
   **14 of 17 diseases now have an env trigger** (up from 9) and **14 of 17 now have a management
   claim** (up from 9) — the biggest single jump in coverage on both fronts so far. Only soybean
   bacterial pustule and soybean mosaic virus remain genuinely open on trigger/advisory after three
   independent research passes — treated as a real literature gap, not a search failure. Loaded and
   promoted live as `kg_2026_10_20`.

---

## 6. Definition of "done" reminder (unchanged from RESEARCH_ROADMAP.md §10)

Keeping this here so status tracking has a target: ≥150 wheat / ≥80 soybean / ≥80 chickpea varieties, ≥250
wheat genes / ≥60 soybean loci / ≥40 chickpea QTLs, ≥3,000 variety-reaction claims, 100% of claims carrying
evidence, ≥80% human-reviewed, extraction precision ≥0.90 / recall ≥0.70 against a hand-built gold set, all 12
competency questions answered, full rebuild in under 20 minutes.

---

## 7. Note on Phases 8 and 11 (renamed scope)

These two phases in `RESEARCH_ROADMAP.md` were written assuming a shared backend. Under the corrected
architecture they become, specifically:

- **Phase 8 (environmental triggers):** GKB's deliverable is the *trigger library itself* —
  `EnvTrigger` entities and `DISEASE_ENV_TRIGGER` claims, each with a numeric envelope, a growth-stage window,
  and a citation, back-tested against historical weather (NASA POWER) for Malwa. What GKB does **not** do is
  watch a live sensor feed — there is no feed here to watch. Whether GKB also offers the stateless
  "match-these-readings" convenience endpoint is Q2.
- **Phase 11 (integration):** becomes "the GKB's outward-facing API for products (a), (b) and (d)" —
  `/v1/features/varieties/{id}` (susceptibility vector), `/v1/priors` (disease plausibility given variety/zone/
  stage), and possibly the Q2 endpoint. It is no longer about a shared database or a shared risk engine.

---

## 8. The query engine (decided 2026-09-25)

The core product ask, restated precisely: farmer/researcher supplies `(crop, variety, field location, sowing
date, optional live sensor reading)` → GKB returns, per relevant disease, a risk level, an evidence-based
confidence tier, and a cited treatment.

- **No LLM at query time.** This is a deterministic lookup-and-score computation over the KG (variety
  susceptibility × environmental-trigger match), not a generation task. An LLM's only role in this system is
  offline, extracting facts into the KG in the first place (Phase 5), always with a mandatory verbatim quote and
  human review before a fact is trusted.
- **One formula, two time-windows.** "May already have occurred" (recent observed readings) and "may occur"
  (weather forecast) are the same `env_match(readings, EnvTrigger) × susceptibility(variety, disease)`
  computation, just fed a look-back window vs. a look-ahead window. The app can show both from one call.
- **GKB owns the weather fetch.** The endpoint takes a location, not pre-fetched weather — GKB calls a free
  forecast API (Open-Meteo) itself and translates the response into its own `EnvTrigger` variable names
  (`config/vocab/sensors.yaml`), so callers never need to learn that mapping.
- **Treatment selection is already variety-aware without a schema change** — `Advisory.action_type` includes
  `varietal` and `monitoring` as well as `chemical`/`cultural`/`biological`, so the same disease can have a
  "spray at stage X" advisory and a "resistant, monitor only" advisory, and the query engine picks the right one
  from the variety's own reaction score.
- **Honesty flag for the UI:** until Phase 8's back-test validates it against real outbreak history, the output
  is a **risk index**, not a calibrated probability — show "high/medium/low" or a 0–100 score, not "70% chance."
- Implementation home: `curator/risk/`, exposed by `api/` as the stateless endpoint from Q2. Not yet built —
  next up is Phase 2's remaining plumbing, then this.
