# AgriHub Genomic KB: Tech Stack and Deployment Decisions

> **Companion to** [RESEARCH_ROADMAP.md](RESEARCH_ROADMAP.md). Where the two disagree on technology, **this file wins**.
> **Date:** 2026-09-25 · **Team size:** 1 (owner builds and runs everything)
> **Target:** a live, public research platform. Researchers use a web dashboard and the API. Farmers use a mobile-friendly app. The IoT and phenomic modules call the API.
>
> ⚠️ **Scope correction, 2026-09-25 — read [PHASES.md](PHASES.md) first.** This repo builds **only** the Genomic
> Knowledge Base — one of four independent products (phenomics on Lightning AI, IoT device with its own Supabase
> project, this GKB, and a separate mobile+dashboard app). Sections below that describe a shared `ops`/ingest
> schema, `/v1/ingest`, or farmer-account tables in **this** Supabase project are **superseded** — the IoT device
> has its own database, not this one. Not yet rewritten pending the open questions in PHASES.md.

---

## 0. Decision summary

| Layer | Current | **Decision** | Why, in one line |
|---|---|---|---|
| Source of truth | The Neo4j graph itself (lost when Aura deleted it) | **Versioned files in git** (`kg/*.tsv`) + releases on Zenodo/R2 | Knowledge survives any database or hosting failure |
| Serving database | Neo4j AuraDB Free | **PostgreSQL** with **PostGIS**, **pg_trgm**, later **pgvector**, managed on **Supabase** (Mumbai region) | One boring database covers graph-shaped facts, maps, fuzzy search, sensor data and embeddings; Supabase adds auth, RLS, realtime and storage you already know |
| Graph | Neo4j as the engine | Graph as the **data model** (entities + claims + evidence tables), plus **graph exports** for researchers | Keeps the KG research value without running a second production database |
| Analytics / ML | none | **DuckDB + Parquet** (offline, notebooks, bulk downloads) | Fast, free, zero-ops |
| API | Cloudflare Pages Functions (JS) → Neo4j HTTPS Query API | **FastAPI (Python 3.12)** in a container on **Google Cloud Run**, with **Cloudflare** in front | One language shared with the pipeline; auto OpenAPI docs; one risk engine instead of a JS port |
| Web dashboard | Vanilla HTML/JS on Cloudflare Pages | **React + Vite + TypeScript** static site on **Cloudflare Pages** | Maps, tables, charts, i18n and a typed API client are necessary for a real dashboard |
| Farmer app | none | **PWA** from the same codebase (installable, offline, Hindi-first); wrap with Capacitor later only if Play Store presence is needed | One codebase for a one-person team |
| IoT ingestion | none | HTTPS batch `POST /v1/ingest` with device keys → Postgres partitioned table | Simpler than running an MQTT broker; fine for tens to hundreds of devices |
| Phenomic model serving | none | **ONNX** model: on-device (ONNX Runtime Web in the PWA) where possible, else a CPU container on Cloud Run | No GPU bill; works offline |
| Files | local disk | **Cloudflare R2** (raw PDFs, genome derivatives, releases, images) | Zero egress fees; cheap |
| Pipeline / cron | manual scripts | `agrihub` CLI; heavy genome jobs run locally; scheduled jobs in **GitHub Actions** | Free, versioned, reproducible |
| Internal curation tool | CLI `input()` loop | **Streamlit** review app, behind **Cloudflare Access** | Fast to build; not public |
| LLM | Groq via urllib, unused Gemini SDK, OpenRouter key | One provider-agnostic client (`httpx`); model ID and prompt version pinned in every evidence row | Reproducibility; free-tier flexibility |
| Auth | none | **Supabase Auth** for dashboard/app users (researchers sign in; farmers anonymous, then phone) · public read endpoints rate-limited · **API keys** for programmatic research access · Cloudflare Access for admin/review | One identity system; FastAPI verifies Supabase JWTs |
| Observability | none | **Sentry** (errors) · Cloud Run logs · uptime monitor · Cloudflare Web Analytics | Free tiers are enough |
| Python | 3.14 locally, 3.11/3.12 in CI | **3.12 everywhere** (Docker image, CI, local via `uv`) | Stop "works on my machine" |

---

## 1. Requirements that drive the choices

| Requirement | Consequence |
|---|---|
| **One developer** | Minimise services and languages. Prefer managed services. No component that needs babysitting. |
| **Live and public** | Nothing may pause or get deleted when idle (Aura Free did, and Supabase Free also pauses idle projects). You need backups, uptime monitoring, and a staging environment. |
| **Researchers** | Stable versioned API, OpenAPI docs, bulk downloads, provenance for every fact, citable releases (DOI), reproducible "KG version X". |
| **Farmers** | Mobile-first, low bandwidth, works offline or on patchy 3G, Hindi and regional languages, simple answers ("risk high for rust this week, why, what to do"), fast responses. |
| **IoT module** | Ingest sensor readings, compute risk windows, return flags with explanations. |
| **Phenomic module** | Image upload/inference; KB priors per variety/zone/stage. |
| **Geography** | Zones, districts and farmer locations are spatial questions (point in polygon, district maps). |
| **Budget** | ₹0 during development; a small, predictable bill (roughly under US$25–40/month) at public launch. |
| **Data size** | Small: ~10⁴–10⁵ claims, ~2×10⁵ reference genes, up to ~10⁶–10⁷ sensor rows per year. |

---

## 2. Audit of the current stack

| Component | Verdict | Problems |
|---|---|---|
| **Neo4j AuraDB Free** | ❌ Replace for production | Pauses on inactivity and deletes paused instances; small node/relationship caps (the full reference gene set alone will not fit); no graph algorithms on Free; the next tier is a big price jump. Your queries are 1–3 hops, which don't need a graph engine. |
| **Pages Functions → Neo4j HTTPS Query API** | ⚠️ Replace | Every request makes a cross-internet HTTP call with Basic auth to Aura (added latency); Neo4j helper code is copy-pasted across 3 files; business logic in JS diverges from the Python pipeline; no API versioning, docs, keys, rate limits or CORS policy. |
| **Vanilla JS frontend** | ⚠️ Replace gradually | Fine for a demo. It will not scale to maps, tables, charts, i18n, offline mode and an evidence viewer without becoming unmaintainable. |
| **Cloudflare Pages hosting** | ✅ Keep | Excellent for static sites: free, fast in India, preview deploys per branch. |
| **Python curator** | ✅ Keep, restructure | The right language for bioinformatics and NLP. Pin 3.12; remove unused dependencies (`gffutils`, `google-generativeai`). |
| **GitHub + Actions** | ✅ Keep | Free CI/cron. |
| **`.env` with 5 keys** | ⚠️ Tidy | Use Cloud Run Secret Manager and GitHub Secrets in deployment. Keep `.env` for local only. |
| **Groq/Gemini/OpenRouter mix** | ⚠️ Consolidate | Put them behind one client interface and log model + prompt version. |

---

## 3. Key decisions and reasoning

### ADR-1: Why PostgreSQL instead of Neo4j

**Context.** The KG's value lies in its **data model** (entities, typed claims, evidence, provenance) and in **exports**, not in a graph engine. The production workload is:
- variety / disease / gene profile pages (1–2 hops),
- the risk calculation (a lookup plus arithmetic),
- search ("HD 3086", "पीला रतुआ" (yellow rust), "Sr31"),
- district/zone maps,
- sensor time windows,
- bulk downloads.

**Postgres covers all of these in one engine:**

| Need | Postgres feature |
|---|---|
| Claims/evidence graph, 1–3 hop queries | Plain joins on indexed foreign keys; materialised views for profiles |
| Pedigrees, gene synonym chains, neighbourhoods | Recursive CTEs (`WITH RECURSIVE`) |
| District/zone maps, "which zone is this farmer in" | **PostGIS** |
| Fuzzy variety/gene search, typo tolerance | **pg_trgm** + full-text search |
| Flexible qualifiers per claim type | `jsonb` with GIN index |
| Sensor readings | Time-partitioned table + BRIN index (TimescaleDB optional later) |
| "Ask the KB" semantic search (later) | **pgvector** |
| Migrations, backups, point-in-time restore, read-only roles | Standard, well documented, managed everywhere |

**What you give up, and how to get it back:**
- *Cypher and graph visualisation.* The dashboard draws neighbourhood graphs with **Cytoscape.js** from a `/v1/graph/neighborhood` endpoint. Researchers get downloadable **graph exports** (KGX TSV, GraphML, and a Neo4j import bundle) with each release.
- *Graph algorithms* (link prediction, centrality). Run them **offline** in Python (NetworkX / PyTorch Geometric) on the release files. That is where research analysis belongs anyway.
- *"Knowledge graph" framing in papers.* This is unaffected: the KG is defined by its schema, identifiers and ontologies, not by its storage engine. Publish it as a KG (KGX/Biolink-style TSV, optional RDF/Turtle).

**Escape hatch:** because the graph is a build artifact, you can later add Neo4j as a **read-only replica** built from the same release files, without redesigning anything.

### ADR-2: Supabase for managed Postgres (decided 2026-09-25, replaces the earlier Neon choice)

**Why Supabase:** you have shipped several full-stack projects on it. For a one-person team, familiarity beats small
technical differences. It is still plain PostgreSQL, so everything in ADR-1 holds. It also adds pieces this
project needs anyway:

| Supabase feature | Used for |
|---|---|
| Postgres + `postgis`, `pg_trgm`, `vector` extensions | KG release schemas, zone maps, fuzzy search, later semantic search |
| **Auth** (email, OAuth, phone OTP, anonymous sign-in) | Researcher accounts on the dashboard; farmers can start anonymously and link a phone later |
| **Row Level Security + auto REST (PostgREST) via `supabase-js`** | User-owned app data (profiles, fields, devices, alerts, saved searches) without writing CRUD endpoints |
| **Realtime** | Live device readings and new risk alerts pushed to the dashboard and PWA |
| **Storage** (private buckets with RLS) | Farmer crop photos for the phenomic model (consented) |
| **`pg_cron`** | Hourly sensor rollups, refreshing materialised views, retention jobs |
| **Supabase CLI** migrations and local stack | Versioned SQL migrations in `supabase/migrations/`; `supabase start` for a local copy (needs Docker) |

**What stays outside Supabase, and why:**
- **FastAPI stays the public, versioned API** (`/v1` KG queries, `/v1/risk`, `/v1/ingest`, `/v1/features`). Researchers need
  a stable contract that doesn't change when table layouts change, plus the Python risk engine and shared pydantic
  models. FastAPI verifies Supabase JWTs for signed-in endpoints, so there is one identity system.
- **Edge Functions:** not used. They would add a third runtime (Deno/TypeScript) to maintain. Use at most one for a webhook if ever needed.
- **Cloudflare R2** for large public files (KG releases, raw PDFs, genome derivatives): zero egress fees. Supabase Storage is only for private user uploads.

**Known limits and how the design handles them:**

| Limit (verify current terms) | Mitigation |
|---|---|
| **Free projects pause after about 1 week without activity** (the Aura failure mode) | (1) The KG is rebuilt from `kg/` files in minutes, so a pause or loss is never fatal. (2) During development, a scheduled GitHub Action does real work weekly (CQ tests against staging), which keeps the project active. (3) **Upgrade production to Pro before public launch.** |
| Free database size is small (~500 MB) | Full reference-gene table stays in DuckDB/Parquet; only NLR/candidate genes go in Postgres. Raw 1-minute sensor data is kept ~90 days, then archived to Parquet on R2; hourly rollups stay in Postgres. |
| Database branching is a paid feature | Two projects instead: `agrihub-staging` (free) and `agrihub-prod` (Pro at launch). KG releases load into a new schema and switch atomically (ADR-7), so no branch is needed for that. |
| Direct DB host is IPv6-only unless you buy the IPv4 add-on | Use the **Supavisor pooler** strings: *transaction mode* (port 6543) for the API on Cloud Run; *session mode* (port 5432) for migrations and `COPY` bulk loads from IPv4-only networks (home ISP, GitHub Actions). |

**Setup (Phase 2, task 2.0).** You create the account and projects yourself, and keep keys out of chat and git.

| Setting | Choice |
|---|---|
| Projects | `agrihub-staging` (free, use for development now) · `agrihub-prod` (create near launch, Pro) |
| Region | **South Asia (Mumbai)**, closest to Indore. Put Cloud Run in `asia-south1` (Mumbai) too. |
| Extensions | enable `postgis`, `pg_trgm` now (Supabase installs them in the `extensions` schema); `vector` later |
| Schemas | `kg_<release>` + `kg_current` views (KG, **not exposed** to PostgREST) · `ops` (ingest, not exposed) · `public` (app tables, **RLS on every table**) · `api` (views you choose to expose, optional) |
| Roles | Supabase built-ins (`anon`, `authenticated`, `service_role`) for app access · custom `pipeline_rw` (loader) and `api_ro` (FastAPI) roles for direct SQL |
| Keys | publishable/anon key → frontend only · secret/service-role key → server only, **never** in the frontend or git |
| Connection strings | `DATABASE_URL` = transaction pooler (API) · `DATABASE_URL_DIRECT` = session pooler (migrations, bulk load) |
| Local development | `supabase start` (Docker) for a full local copy, **or** work directly against `agrihub-staging`. Unit and CQ tests use a throwaway local Postgres, and CI uses a Postgres service container, so tests never touch Supabase. |
| Backups | Supabase daily backups (Pro) + nightly `pg_dump` of prod to R2 (GitHub Action) + canonical `kg/` files in git |

### ADR-3: Why a FastAPI container instead of Cloudflare Functions

- **One language.** The same `pydantic` models (from `curator/model/`), normalisers, **risk engine** and confidence scorer are imported by the pipeline *and* the API. Without this you would maintain the risk engine twice (the JS port in the roadmap's Phase 8.4 is no longer needed).
- **OpenAPI for free.** Interactive docs at `/docs` for researchers; typed TypeScript client generated for the dashboard (`openapi-typescript`); property-based API testing with **Schemathesis**.
- **Mature DB access** (psycopg 3 / asyncpg through the Supabase transaction pooler). Migrations for app/ops tables use the **Supabase CLI** (`supabase/migrations/*.sql`); KG release schemas are created by the loader.
- **Cloud Run** scales to zero, has a generous free request allowance, deploys from a Dockerfile, and holds secrets in Secret Manager. At launch, set **min-instances = 1** to remove cold starts for farmers (a small monthly cost).
- **Keep Cloudflare in front** (DNS, TLS, CDN caching of GET responses, WAF, rate-limiting rules). Most farmer reads (variety/disease pages) are cacheable for minutes to hours, so the backend stays quiet and cheap.

### ADR-4: One frontend codebase: dashboard + farmer PWA

- **React + Vite + TypeScript**, deployed as static files on Cloudflare Pages.
- Libraries: **TanStack Query** (API caching), **TanStack Table** (research tables), **MapLibre GL JS** (free maps; district/zone risk layers), **Apache ECharts** (charts), **Cytoscape.js** (graph neighbourhood view), **i18next** (English, Hindi, then Marathi/others), **vite-plugin-pwa** (offline cache, installable).
- Two route groups in one app:
  - `/farm/*`: large text, icons, local language, "my field" (variety + location + sowing date), weekly risk card with a reason and an advisory. Works offline from cached data.
  - `/research/*`: search, profiles, evidence drawer with quotes and citations, filters, downloads, API key page, KG release selector.
- Why not Streamlit/Dash for the public dashboard: they are slow on mobile, have weak offline/i18n support, and are hard to make farmer-friendly. Use Streamlit **only** for the internal review tool.
- Why not native Android: a solo developer cannot maintain two apps. A PWA covers Android Chrome well. Wrap it with Capacitor only if Play Store distribution becomes necessary.
- Farmer notifications: **Web Push** (Android) first. **SMS/WhatsApp** alerts cost money per message; add them later with a provider.

### ADR-5: IoT ingestion

- Devices (e.g., ESP32) buffer readings and `POST /v1/ingest` every 15–30 minutes over HTTPS with a per-device key (store only a hash). Payload: device_id, readings[] (ts, air_temp, rh, leaf_wetness, soil_moisture, soil_temp, rain).
- Store readings in a `sensor_reading` table **partitioned by month** with a BRIN index on `ts`, and a rollup table (hourly aggregates) feeding the risk engine.
- The risk engine runs **on ingest** (or hourly via Cloud Scheduler) and writes `field_risk` rows, which drive app notifications.
- Skip MQTT for now. Add a managed broker only if you need device commands or sub-minute data.
- Keep raw 1-minute readings ~90 days in Postgres, then archive them to Parquet on R2 (a `pg_cron` or GitHub Action job). Hourly rollups stay in Postgres. **Supabase Realtime** pushes new readings and alerts to the dashboard.

### ADR-6: Phenomic model serving

- Export the trained model to **ONNX** (quantised INT8 where accuracy allows).
- Preferred: **on-device inference** in the PWA (ONNX Runtime Web). It works offline, costs nothing to serve, and keeps farmer photos private.
- Fallback: a CPU inference container on Cloud Run (`POST /v1/diagnose`), which fuses the model's probabilities with the **KB prior** from `/v1/features`.
- Store images only with consent, in a **private Supabase Storage bucket** with RLS (owner-only), under a data policy.

### ADR-7: Knowledge release model ("blue/green data")

- `agrihub kg build` produces release `kg-YYYY.MM.N` (TSVs + manifest).
- `agrihub kg load --release kg-2026.10.1` loads into a **new Postgres schema** `kg_2026_10_1`, runs the competency-question tests and QC against it, then atomically repoints the `kg_current` views (or the API's configured schema). **Rollback = repoint.**
- Every API response includes `kg_release`. Researchers can pin `?release=` to the previous 2–3 releases, which keeps their results reproducible.
- Every release is uploaded to Zenodo (DOI) and R2 (download links in the dashboard).

---

## 4. Target deployment architecture

```
                         Cloudflare (DNS · TLS · CDN cache · WAF · rate limits · Web Analytics)
                                   │                                   │
               ┌───────────────────┴──────────┐              ┌─────────┴───────────┐
               ▼                              ▼              ▼                     ▼
   Cloudflare Pages (static)          api.<domain>     Cloudflare Access     R2 bucket
   React/Vite PWA                     Cloud Run:       (admin + review)      releases · raw PDFs
   /farm/*  /research/*               FastAPI /v1      Streamlit review      genome derivatives
               │   fetch (typed client)    │           app (Cloud Run)       images (consented)
               └──────────────────────────►│                  │
                                           ▼                  ▼
                                  Supabase PostgreSQL (Mumbai) ◄── pipeline writes (pipeline_rw)
                                  + Auth · RLS/PostgREST · Realtime · Storage · pg_cron
                                  PostGIS · pg_trgm · jsonb · partitions · (pgvector)
                                  schemas: kg_<release> + kg_current views, ops (keys, devices,
                                  sensor readings, field risk), audit
                                           ▲
   IoT devices ── HTTPS batch ─────────────┘ /v1/ingest
   GitHub Actions: tests · build image · deploy · scheduled lit refresh · nightly pg_dump → R2
   Laptop: heavy genome parsing (GFF → Parquet → R2), LLM extraction runs, review
```

**Environments**

| Env | Database | API | Frontend |
|---|---|---|---|
| local | `supabase start` (Docker) or `agrihub-staging`; tests use a throwaway Postgres | `uvicorn --reload` | `vite dev` |
| staging | Supabase project `agrihub-staging` | Cloud Run `agrihub-api-staging` | Pages preview URL |
| production | Supabase project `agrihub-prod` (Pro) | Cloud Run `agrihub-api` (min 1 instance at launch) | Pages production + custom domain |

---

## 5. Postgres data model (sketch)

The KG is stored as typed core tables plus a generic claim/evidence layer (a property graph inside relational tables).

```sql
-- per release schema: kg_2026_10_1
CREATE TABLE entity (
  id           text PRIMARY KEY,            -- 'var:wheat:HD3086', 'gene:wheat:Lr34'
  type         text NOT NULL,               -- Variety|Gene|QTL|Marker|Disease|Pathogen|Pathotype|EnvTrigger|...
  crop         text,
  name         text NOT NULL,
  props        jsonb NOT NULL DEFAULT '{}',
  name_i18n    jsonb NOT NULL DEFAULT '{}'  -- {"hi": "...", "mr": "..."}
);
CREATE INDEX ON entity USING gin (name gin_trgm_ops);
CREATE INDEX ON entity (type, crop);

CREATE TABLE entity_synonym (entity_id text REFERENCES entity, synonym text, source text);
CREATE INDEX ON entity_synonym USING gin (synonym gin_trgm_ops);

CREATE TABLE publication (id text PRIMARY KEY, doi text, pmid text, title text, year int,
                          journal text, license text, verified boolean NOT NULL);

CREATE TABLE claim (
  id          text PRIMARY KEY,
  type        text NOT NULL,                -- VARIETY_REACTION, GENE_CONFERS_RESISTANCE, ...
  subject_id  text NOT NULL REFERENCES entity,
  object_id   text NOT NULL REFERENCES entity,
  qualifiers  jsonb NOT NULL,               -- reaction, stage, pathotype, location, season...
  score       real NOT NULL, tier char(1) NOT NULL, conflict boolean NOT NULL DEFAULT false,
  status      text NOT NULL                 -- reviewed | unreviewed | predicted
);
CREATE INDEX ON claim (subject_id, type); CREATE INDEX ON claim (object_id, type);
CREATE INDEX ON claim USING gin (qualifiers);

CREATE TABLE evidence (
  id text PRIMARY KEY, claim_id text REFERENCES claim, source_id text, locator text,
  quote text, method_eco text, extractor text, reviewer text, reviewed_at timestamptz, weight real
);

-- domain tables where typed columns matter
CREATE TABLE ref_gene (locus_id text PRIMARY KEY, crop text, assembly text, chrom text,
                       start_bp bigint, end_bp bigint, strand char(1), description text,
                       domains text[], is_nlr boolean, nlr_class text);
CREATE INDEX ON ref_gene (crop, chrom, start_bp);
CREATE TABLE env_trigger (id text PRIMARY KEY, disease_id text, phase text, stage_from int, stage_to int,
                          conditions jsonb, zones text[], backtest jsonb);
CREATE TABLE zone (id text PRIMARY KEY, crop text, name text, geom geometry(MultiPolygon, 4326));
CREATE INDEX ON zone USING gist (geom);

-- fast read models
CREATE MATERIALIZED VIEW variety_profile AS ...;  -- variety + reactions + genes + zones, one JSON document per variety
CREATE MATERIALIZED VIEW disease_profile AS ...;

-- ops schema (not versioned per release)
-- ops.api_key, ops.device, ops.sensor_reading (partitioned by month), ops.sensor_hourly,
-- ops.field, ops.field_risk, ops.audit_log
```

The competency questions from the roadmap become **SQL** (tested in `tests/cq/`). Keep Appendix A's Cypher only as documentation of the graph semantics.

---

## 6. Hosting options and cost

**Option A (recommended): managed and serverless**

| Service | Dev / beta | Public launch (approximate) |
|---|---|---|
| Cloudflare Pages + DNS + CDN + WAF + Access (≤ 50 users) | Free | Free |
| Cloudflare R2 | Free tier (~10 GB, no egress fees) | A few $ as data grows |
| Cloud Run (API + review app) | Free tier | ~$5–15/month with min-instances = 1 |
| Supabase | Free (staging) | ~$25/month Pro for prod (no pausing, daily backups, more storage; includes a small compute credit) |
| Sentry, uptime monitor, GitHub Actions (public repo) | Free | Free |
| Domain | — | ~$10–15/year |
| **Total** | **$0** | **~$25–40/month** |

**Option B: institute server or a single VPS.** If IIT Indore can give you a VM (ask; it also gives an institutional URL and longevity beyond your tenure), run Docker Compose with **Caddy (TLS) + FastAPI + PostGIS**, nightly `pg_dump` to R2, and unattended security updates. Keep Cloudflare in front. This is cheaper at scale, but you own operations and uptime.

**Avoid:** Kubernetes, microservices, self-hosted Kafka/MQTT/Elasticsearch, running Neo4j and Postgres both in production, and paid GPU hosting.

*All prices and free-tier limits are approximate and change often. Verify them at signup and record the date.*

---

## 7. API design (v1)

- Base path `/v1`, JSON, snake_case, ISO dates. All responses include `kg_release` and `request_id`.
- **Public (no key, rate-limited):**
  - `GET /v1/search?q=&crop=&type=`
  - `GET /v1/varieties/{id}`, `/v1/diseases/{id}`, `/v1/genes/{id}`
  - `GET /v1/claims/{id}` (evidence and quotes)
  - `GET /v1/graph/neighborhood?id=&depth=1..2`
  - `POST /v1/risk` (sensor window or location + dates → flags with explanations)
  - `GET /v1/zones/lookup?lat=&lon=`
  - `GET /v1/stats`
- **Researcher key (higher limits):**
  - `GET /v1/claims?type=&crop=&tier>=&updated_since=` (paginated with cursors)
  - `GET /v1/features/varieties/{id}`
  - `GET /v1/releases` (+ download links)
- **Device key:** `POST /v1/ingest`
- **Admin (behind Cloudflare Access):** `/v1/admin/*` (reload release, rotate keys)
- Caching: profile GETs send `Cache-Control: public, max-age=3600` and an ETag keyed by release. `/risk` and `/ingest` are uncacheable.
- Errors follow RFC 9457 (`application/problem+json`).
- Documentation: FastAPI `/docs` + `/redoc`, plus a hand-written "Getting started for researchers" page with example `curl`/Python/R snippets and the citation text.

---

## 8. Security and data governance (solo-friendly minimum)

- **Database roles:** `api_ro` (SELECT on `kg_current` + INSERT on `ops.sensor_reading`/`ops.field_risk` only), `pipeline_rw`, `admin`. The API never holds DDL rights.
- Parameterised SQL only; pydantic validates every request; payload size limits.
- API keys and device keys stored as **hashes**; per-key rate limits (Cloudflare rules + `slowapi`).
- CORS allowlist (your domains only). HTTPS everywhere. Secrets live in GitHub Secrets and Cloud Run Secret Manager.
- `pre-commit` with `detect-secrets`, `ruff`, `mypy`; Dependabot for dependencies.
- **Backups:** Supabase daily backups (Pro), plus a nightly `pg_dump` to R2 (keep 30 days), plus canonical files in git/Zenodo. **Test a restore every quarter.**
- **Supabase specifics:** RLS enabled on every `public` table (no exceptions); KG and ops schemas not exposed to PostgREST; the secret/service-role key only in server-side secrets.
- **Farmer data:** collect the minimum (field location at village/district precision, variety, sowing date). Get consent. Publish a privacy notice aligned with India's DPDP Act. No personal data in logs.
- **Advice disclaimer:** risk flags are decision support, and chemical advice comes only from official Package-of-Practices sources with a citation shown.
- **Licences:** data CC-BY 4.0 (respecting source licences), code MIT/Apache-2.0, `CITATION.cff`.

---

## 9. Developer tooling

| Purpose | Tool |
|---|---|
| Python env and locking | **uv** (`uv sync`, `uv.lock`), Python 3.12 |
| Lint / format / types | ruff, mypy (strict on `curator/model`, `api/`) |
| DB migrations | Supabase CLI (`supabase migration new`, `supabase db push`) for `public`/`ops`; the release loader creates the `kg_*` schemas |
| Tests | pytest, pytest-postgresql or Testcontainers, Schemathesis (API), Playwright (a few end-to-end flows) |
| Frontend | pnpm, Vite, TypeScript strict, ESLint, Vitest |
| CI/CD | GitHub Actions: lint → test → build image → deploy staging → manual approval → prod |
| Local services | `docker compose up` (postgis, api, review app) |
| Notebooks | Jupyter + DuckDB for the analysis in `analysis/` |

---

## 10. Migration plan from the current code

| Step | What | Maps to roadmap |
|---|---|---|
| M1 | Pin Python 3.12 with `uv`; drop `gffutils` and `google-generativeai`; add FastAPI, psycopg, pydantic, duckdb, supabase CLI | Phase 0 |
| M2 | ✅ `supabase init` done (`supabase/` scaffold + `migrations/20260925081644_enable_extensions.sql`, run manually in the SQL Editor). Remaining: migration for the `ops` and `public` app tables (with RLS) | Phase 2 |
| M3 | Replace the Neo4j loader with the **Postgres release loader** (schema-per-release, COPY from TSV, materialised views, `kg_current` repoint). Delete `curator/db.py`, `load_genes.py`, `seed_loader.py`, `init_constraints.py`. | Phase 2 (tasks 2.3/2.4) |
| M4 | New `api/` package (FastAPI) importing `curator.model` and `curator.risk`; implement `/v1/stats`, `/v1/search`, `/v1/varieties/{id}` first | Phase 10 (start early) |
| M5 | Dockerfile + Cloud Run staging deploy (asia-south1) via GitHub Actions; Supabase `agrihub-staging` project; Cloudflare DNS `api.` subdomain | Phase 2/10 |
| M6 | Delete `functions/api/*.js` and `wrangler.toml` once the dashboard calls the new API | Phase 10 |
| M7 | New `web/` (React/Vite/TS PWA) replacing `public/`; generated API client; research profile pages first, farmer pages second | Phase 10 |
| M8 | `/v1/ingest` + `ops.sensor_*` + risk job | Phase 8/11 |
| M9 | Streamlit review app behind Cloudflare Access | Phase 5 (task 5.10) |
| M10 | Nightly backup workflow, Sentry, uptime monitor, status page | Before public launch |

**Launch checklist:** restore test passed · rate limits on · CORS locked · min-instances = 1 · uptime alert to your phone · privacy notice and disclaimer published · API docs + citation page live · release `kg-v1.0.0` has a DOI.

---

## 11. Target repository layout (updated)

```
gkb-v1/
├── curator/           (pipeline: model, normalize, genome, lit, nlp, llm, extract, trials, risk, graph)
├── api/               (FastAPI app: routers/, deps.py, settings.py; imports curator.model & curator.risk)
├── web/               (React + Vite + TS PWA: src/farm, src/research, src/api-client generated)
├── tools/review_app/  (Streamlit, internal)
├── db/                (KG release schema DDL, CQ queries, release loader SQL)
├── kg/                (canonical versioned knowledge files + manifest)
├── eval/  analysis/  tests/  docs/
├── supabase/          (config.toml, migrations/ for public + ops schemas, seed.sql)
├── Dockerfile  pyproject.toml  uv.lock
└── .github/workflows/ (ci.yml, deploy.yml, kg-release.yml, lit-refresh.yml, backup.yml)
```
