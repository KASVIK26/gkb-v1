# AgriHub Genomic Knowledge Base

The genomic module of AgriHub: an evidence-backed knowledge base linking **wheat, soybean and chickpea**
varieties, resistance genes/QTLs, diseases, pathotypes and the environmental conditions that trigger disease.
It feeds the IoT risk engine and the phenomic/yield models.

> **Status: restarting. Phases 0 and 1 done (2026-09-25). Next: Phase 2 (Supabase + release build).** The v1 graph and its seed data were found to be unreliable
> and have been archived. See the plan before changing anything.

| Document | Purpose |
|---|---|
| [PHASES.md](PHASES.md) | **Start here.** What's done, what's next, open questions — for this repo (Genomic KB) only |
| [RESEARCH_ROADMAP.md](RESEARCH_ROADMAP.md) | Audit findings and the phase-by-phase plan (source of truth for *what* to build) |
| [TECH_STACK.md](TECH_STACK.md) | Stack and deployment decisions (source of truth for *how*) |
| [docs/genomic_datasets.md](docs/genomic_datasets.md) | Survey of additional genomic datasets (pangenomes, SNP arrays, resequencing panels) and why they're deferred for now |
| [config/sources/candidate_papers.yaml](config/sources/candidate_papers.yaml) | Verified reading list — real, checked papers per disease, triage input for Phase 5 |
| [config/sources/notified_varieties.yaml](config/sources/notified_varieties.yaml) | Notified wheat/soybean/chickpea varieties for MP/Malwa, tiered by confidence |
| `docs/archive/` | Superseded v1 plans (PROJECT.md, FUTURE_VISION.md, NEXT_PHASE_TASKS.md, SETUP_GUIDE.md) |
| `archive/legacy_v1/` | The v1 seed edges and loaders. **Do not load them.** |

## Local setup

Requires Python **3.12** (pinned in `.python-version` and `pyproject.toml`).

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\pre-commit.exe install      # enables the secret scanner on every commit
```

Copy `.env.example` to `.env` and fill in the keys you need. `.env` is gitignored.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -m "not integration"
```

Schema and competency-question tests start a throwaway local PostgreSQL automatically (or use
`TEST_DATABASE_URL`). They never touch your running servers or Supabase. `-m integration` tests need a live database. They target the legacy Neo4j setup and are replaced by Postgres tests in Phase 2.

## Data

- `data/` is gitignored except `data/manifests/`. Raw genomes and papers live in `data/raw/` and are never committed.
- Genome annotations in use: IWGSC CS RefSeq v2.1 (wheat, NCBI GFF + assembly report), Wm82 gnm6 (soybean, LIS GFF3),
  ICC4958 gnm2.ann1 (chickpea, LIS GFF3). Registered in `config/datasets.yaml`.

## Current code (legacy, being replaced)

`curator/` holds the v1 parsers (GFF3, assembly report, GBFF) and a Groq-based paper extractor. The parsers
carry forward into Phase 4; the extractor is replaced in Phase 5.

`curator/graph/`, `curator/model/` and `curator/normalize/` are the **current**, Postgres/Supabase-based KG
pipeline (`agrihub kg build/load/promote/current`) — not legacy.

`functions/` and `public/` were the v1 Cloudflare Pages demo (Neo4j-backed) and have been **rewritten
(2026-09-26)** against the live Supabase KG via `public.kg_*` bridge views
(`supabase/migrations/20260926120000_dashboard_views.sql`) — see [public/README.md](public/README.md) for
what it can do and how to run it locally. It is a demo query layer, not the real risk-engine API
(RESEARCH_ROADMAP.md Phase 11, not built yet).
