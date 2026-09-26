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
| 4 | Genomic layer: NLR candidates, QTL anchoring from your 3 genome files | ⬜ Not started |
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
