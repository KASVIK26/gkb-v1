# AgriHub Genomic Knowledge Base

The genomic module of AgriHub: an evidence-backed knowledge base linking **wheat, soybean and chickpea**
varieties, resistance genes/QTLs, diseases, pathotypes and the environmental conditions that trigger disease.
It feeds the IoT risk engine and the phenomic/yield models.

> **Status: restarting (Phase 0 done, 2026-09-25).** The v1 graph and its seed data were found to be unreliable
> and have been archived. See the plan before changing anything.

| Document | Purpose |
|---|---|
| [RESEARCH_ROADMAP.md](RESEARCH_ROADMAP.md) | Audit findings and the phase-by-phase plan (source of truth for *what* to build) |
| [TECH_STACK.md](TECH_STACK.md) | Stack and deployment decisions (source of truth for *how*) |
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

`-m integration` tests need a live database. They target the legacy Neo4j setup and are replaced by Postgres tests in Phase 2.

## Data

- `data/` is gitignored except `data/manifests/`. Raw genomes and papers live in `data/raw/` and are never committed.
- Genome annotations in use: IWGSC CS RefSeq v2.1 (wheat, NCBI GFF + assembly report), Wm82 gnm6 (soybean, LIS GFF3),
  ICC4958 gnm2.ann1 (chickpea, LIS GFF3). Registered in `config/datasets.yaml`.
- `data/quarantine/` holds the files removed in Phase 0 (irrelevant papers, the gene-less chickpea GBFF,
  hallucinated review queue). See its README, then delete it.

## Current code (legacy, being replaced)

`curator/` holds the v1 parsers (GFF3, assembly report, GBFF), a Groq-based paper extractor and Neo4j loaders.
`functions/` and `public/` hold the v1 Cloudflare Pages demo. The parsers carry forward into Phase 4. The loaders,
extractor and Pages Functions are replaced in Phases 2, 5 and 10.
