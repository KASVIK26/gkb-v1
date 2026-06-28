# AgriHub Genomic Knowledge Base — Project Brief

**Project codename:** AgriHub-KB
**Owner:** Vikas (IIT Indore AgriHub research intern)
**Purpose of this document:** Hand this entire file to GitHub Copilot / Copilot Chat as project context before starting work. It defines scope, architecture, phases, and task-by-task instructions so Copilot can generate code consistent with one plan instead of improvising a new structure every session.

---

## 1. Project objective

Build an automated, incrementally-growing genomic knowledge base for crop disease resistance across wheat, soybean, and chickpea — covering variety → resistance gene/QTL → target disease → recommended action — queryable through a public web interface, backed by a real graph database, and populated by a repeatable curator pipeline rather than one-off manual entry.

This is **not** a one-time data dump. The defining feature is the curator pipeline: every time a new dataset, paper, or genome annotation file is added, the pipeline extracts structured entities and relationships and writes them into the graph automatically, so the knowledge base grows over the project's lifetime instead of being rebuilt from scratch.

## 2. Non-negotiable architecture decision

**The browser never talks to Neo4j directly.** AuraDB credentials must never be shipped in client-side JavaScript — anyone opening browser dev tools on the live site would get write access to the database. All UI tools that suggest "connect Neo4j on the frontend" usually mean *this* pattern:

```
Browser (Cloudflare Pages, static HTML/JS)
        │  fetch('/api/query', { variety, crop })
        ▼
Cloudflare Pages Function  (free tier — same project as the static site)
        │  holds NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD as encrypted secrets
        │  runs parameterized, read-only Cypher
        ▼
Neo4j AuraDB Free  (50,000 nodes / 175,000 relationships — far more than this project needs)
```

The curator pipeline (Section 5) is a **separate, offline process** — it runs on your laptop or in Google Colab, connects to AuraDB directly using the official Python driver, and writes data. It is never exposed to the public internet and is not part of the deployed web app.

## 3. Tech stack (all free tier, no credit card required for any of it)

| Layer | Tool | Why |
|---|---|---|
| Graph database | Neo4j AuraDB Free | 50K nodes / 175K relationships free forever, managed, no ops |
| Curator pipeline | Python 3.11+, `neo4j` driver, `gffutils`, `pandas` | Standard bioinformatics + graph tooling |
| AI extraction | Google Gemini API (`gemini-2.5-flash` or `gemini-flash-lite`) | Free tier, generous daily request quota, good at structured JSON extraction |
| Fallback AI extraction | GitHub Copilot Chat (via student pack) | Use interactively while writing/debugging pipeline code, not as a batch API — Copilot is not designed for unattended batch calls |
| API layer | Cloudflare Pages Functions | Free, deploys with the static site, holds secrets safely |
| Frontend hosting | Cloudflare Pages | Free, fast, the existing prototype already fits this |
| Frontend code | Plain HTML/CSS/JS (already built — `AgriHub_KB_Prototype.html`) | No build step needed; can evolve to fetch from the API layer instead of the local `kb_data.js` |
| Version control | GitHub | Required for Cloudflare Pages auto-deploy and for Copilot to have repo context |

**Do not introduce:** a Node/Express backend, Docker, or any paid hosting tier. Everything above has a genuinely free, no-card-required tier as of mid-2026 — re-verify limits before relying on them if this project runs long, since free-tier terms shift.

## 4. Repository structure

```
agrihub-kb/
├── PROJECT.md                  # this file
├── config/
│   └── datasets.yaml           # registry of dataset file paths + metadata (Section 5.1)
├── data/
│   └── raw/                    # downloaded GFF3/FASTA/VCF — gitignored, never committed
├── curator/
│   ├── parsers/
│   │   ├── gff_parser.py       # extracts gene models + coordinates from GFF3
│   │   └── vcf_parser.py       # extracts SNP positions (added later, optional)
│   ├── extractors/
│   │   └── paper_extractor.py  # sends paper text to Gemini, returns structured JSON
│   ├── schema.py                # canonical node/relationship schema (Section 6)
│   ├── loader.py                # writes parsed/extracted records into Neo4j via Cypher
│   ├── validator.py             # checks for duplicate genes, conflicting confidence, orphan nodes
│   └── run_pipeline.py          # CLI entrypoint: orchestrates parse → extract → validate → load
├── functions/
│   └── api/
│       └── query.js             # Cloudflare Pages Function — the only thing that talks to Neo4j
├── public/
│   ├── index.html               # the web interface (evolve from AgriHub_KB_Prototype.html)
│   └── app.js
├── tests/
│   └── test_loader.py
├── .env.example                 # NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, GEMINI_API_KEY — never commit real .env
├── requirements.txt
└── README.md
```

## 5. The curator pipeline — how it actually works

### 5.1 Dataset registry (`config/datasets.yaml`)

Every dataset gets registered here with its local path and metadata **before** the pipeline touches it. This is the "add the path in my project" step:

```yaml
datasets:
  - id: wheat_iwgsc_gff3
    crop: wheat
    type: gene_annotation
    local_path: data/raw/iwgsc_refseqv2.1_gene_annotation.gff3
    source: "IWGSC / URGI INRAE, PRJNA392179"
    status: not_downloaded   # not_downloaded | downloaded | parsed | loaded

  - id: soybean_wm82_v6
    crop: soybean
    type: reference_assembly
    local_path: data/raw/wm82_a6_v1.fasta
    source: "USDA-ARS / Iowa State University, GCA_002905335"
    status: not_downloaded

  - id: chickpea_icc4958
    crop: chickpea
    type: reference_assembly
    local_path: data/raw/icc4958_desi.fasta
    source: "ICRISAT / BGI, PRJNA256933"
    status: not_downloaded
```

You update `status` manually as you download each file. The pipeline reads this file at the start of each run and only processes datasets marked `downloaded` — this is what lets you add datasets incrementally without re-running everything.

### 5.2 Automated step sequence (per dataset)

1. **Parse** — `gff_parser.py` reads the GFF3, extracts gene IDs, chromosome, start/end coordinates, and any functional annotation (GO/IPR terms). Writes an intermediate `data/processed/<dataset_id>_genes.json`.
2. **Extract relationships** — `paper_extractor.py` takes a literature source (paper abstract, dataset README, or a manually pasted excerpt) and asks Gemini to return strict JSON matching the schema in Section 6 — gene, disease, pathogen, resistance type, varieties, confidence, IoT trigger, treatment. This is where most "knowledge" enters the graph; the genome files mostly supply coordinates.
3. **Validate** — `validator.py` checks: no duplicate gene+disease edge from the same source, confidence is one of the allowed enum values, every variety referenced exists as a node, no missing required fields. Flags anything uncertain into a `review_queue.json` instead of silently loading it.
4. **Load** — `loader.py` takes validated records and runs idempotent `MERGE` Cypher statements (never `CREATE`, to avoid duplicate nodes on re-runs) against AuraDB.
5. **Update registry** — `run_pipeline.py` flips the dataset's `status` to `loaded` in `datasets.yaml` once step 4 succeeds.

This sequence is what "increase knowledge graph after each automated step" means in practice — each dataset goes through the same five gates, and the graph only grows by validated, idempotent writes.

### 5.3 Where Gemini and Copilot each fit

- **Gemini (via API key, used inside `paper_extractor.py`)** — batch, unattended, structured-output extraction from text. This is a programmatic API call your pipeline makes, not a chat session.
- **Copilot (via your student pack, used inside your editor)** — writing and debugging the pipeline code itself, generating Cypher query drafts, writing test cases, explaining gffutils/Neo4j driver errors. Copilot is an interactive coding assistant, not something you call from inside a script.

Don't conflate the two: Gemini does the data extraction *at runtime*; Copilot helps you *write the code* that calls Gemini.

## 6. Graph schema (canonical — do not let this drift between sessions)

**Node labels:**
- `Crop {name}` — Wheat / Soybean / Chickpea
- `Variety {name, crop}` — e.g. "Chinese Spring"
- `Gene {id, chromosome, allele, resistance_type}` — e.g. "Sr33"
- `Disease {name, pathogen}` — e.g. "Stem Rust"
- `Treatment {action, iot_trigger}`
- `Dataset {id, source, type}` — provenance node, links back to `config/datasets.yaml` entries

**Relationships:**
- `(Variety)-[:BELONGS_TO]->(Crop)`
- `(Variety)-[:CARRIES {confidence}]->(Gene)`
- `(Gene)-[:CONFERS_RESISTANCE_TO {confidence}]->(Disease)`
- `(Disease)-[:TREATED_BY]->(Treatment)`
- `(Gene)-[:SOURCED_FROM]->(Dataset)`

This mirrors the existing Gene–Disease Map structure from the original Excel KB, just normalized into a graph. Keep `confidence` as an edge property (`Very High` / `High` / `Medium`) — don't invent new enum values without updating this schema doc first.

## 7. API layer contract (`functions/api/query.js`)

One endpoint, read-only, parameterized — never string-concatenate Cypher with user input:

```
POST /api/query
Body: { "crop": "wheat", "variety": "Chinese Spring" }   // variety: "__all__" for full crop map
Response: { "edges": [ { gene, chromosome, allele, disease, pathogen,
                          resistanceType, confidence, treatment, iotTrigger, varieties } ] }
```

The frontend's existing `kb_data.js` static object becomes the **shape contract** for this response — Copilot should make the API return data in that same shape so `public/app.js` barely changes.

## 8. Phased task list for Copilot

### Phase 0 — Repo and account setup (you do this manually, ~30 min)
- [ ] Create GitHub repo `agrihub-kb`, push the structure in Section 4
- [ ] Create free Neo4j AuraDB instance, save connection URI + credentials somewhere safe (not in the repo)
- [ ] Get a Gemini API key from Google AI Studio (no card required)
- [ ] Connect the GitHub repo to Cloudflare Pages (free, auto-deploys on push)

### Phase 1 — Schema and empty graph
- [ ] Write `curator/schema.py` defining the node/relationship constants from Section 6
- [ ] Write a one-time `curator/init_constraints.py` that creates uniqueness constraints in AuraDB (`Gene.id`, `Variety.name+crop`, `Disease.name`) — prevents duplicate nodes from the start
- [ ] Verify connection from local Python to AuraDB using the official `neo4j` driver

### Phase 2 — Seed load from existing curated data
- [ ] Write `curator/loader.py` with idempotent `MERGE` Cypher
- [ ] Load the 22 existing gene-disease edges (from the prior Excel/`kb_data.js`) as the first seed — this proves the pipeline end-to-end before any new extraction happens
- [ ] Confirm in AuraDB Browser that nodes/relationships match Section 6 schema

### Phase 3 — GFF3 parser (genomic coordinates)
- [ ] Write `curator/parsers/gff_parser.py` using `gffutils`
- [ ] Test against the wheat IWGSC GFF3 once downloaded — extract gene ID, chromosome, start/end for genes matching known resistance gene names (Sr33, Yr18, etc.)
- [ ] Write the coordinates onto existing `Gene` nodes as properties (`MERGE` + `SET`, don't duplicate)

### Phase 4 — AI extraction pipeline
- [ ] Write `curator/extractors/paper_extractor.py` — function that takes raw text (paper abstract/excerpt) and a Gemini API key, returns JSON matching Section 6 schema, with a strict system prompt forcing JSON-only output and a fixed field list
- [ ] Add retry/backoff for Gemini 429 rate-limit errors (free tier is ~10-15 requests/minute — see Section 3)
- [ ] Add a human-review step: extracted records go into `review_queue.json` first; you approve before they reach `loader.py`
- [ ] Run on 5-10 real papers to add new genes/diseases beyond the original 22 edges

### Phase 5 — Validation layer
- [ ] Write `curator/validator.py`: schema conformance, duplicate detection, confidence enum check
- [ ] Wire it into `run_pipeline.py` so nothing reaches `loader.py` unvalidated

### Phase 6 — API layer
- [ ] Write `functions/api/query.js` as a Cloudflare Pages Function
- [ ] Store `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` as Cloudflare Pages environment variable secrets (never in code)
- [ ] Use the Neo4j JavaScript driver (or HTTPS Query API per Section 9 note) to run read-only parameterized Cypher
- [ ] Return JSON in the exact shape Section 7 specifies

### Phase 7 — Frontend integration
- [ ] Modify `public/app.js` (evolved from the existing prototype) to `fetch('/api/query', ...)` instead of reading the local `KB` object
- [ ] Keep the existing UI untouched — crop dropdown, variety dropdown, optional IoT toggle, edge cards
- [ ] Add a loading state for the fetch call (the static prototype was instant; a real API call has latency)

### Phase 8 — Deploy and verify
- [ ] Push to GitHub, confirm Cloudflare Pages auto-deploys
- [ ] Test live site end-to-end: select wheat → Chinese Spring → confirm 3 edges load from AuraDB, not from a local file
- [ ] Confirm browser dev tools → Network tab shows no database credentials anywhere in the response or request

### Phase 9 — Incremental growth loop (ongoing, this is the actual point of the project)
- [ ] Add a new dataset to `config/datasets.yaml`, download it, flip status to `downloaded`
- [ ] Run `python curator/run_pipeline.py` — it should pick up only the new dataset, parse/extract/validate/load it, and leave everything else untouched
- [ ] Confirm node/relationship counts in AuraDB increased by exactly the new dataset's contribution

## 9. Open implementation notes for Copilot to resolve

- **Neo4j driver in Cloudflare Workers:** the standard `neo4j-driver` package is designed for Node.js and may not run cleanly in the Workers V8 isolate runtime. Investigate whether Neo4j's HTTPS Query API (works over plain `fetch`, no Bolt/WebSocket needed — see `https://neo4j.com/docs/aura/...`) is a better fit for a Cloudflare Pages Function than the Bolt driver. Decide this in Phase 6 before writing `query.js`, not after.
- **Gemini free-tier rate limits change frequently** (Google adjusted them multiple times across 2025-2026). Before running any batch extraction job, check current RPM/RPD limits in Google AI Studio rather than trusting a number from an old blog post — Section 3's numbers are a planning baseline, not a guarantee.
- **Confidence values are literature-derived, not computed.** Don't let any future automated step silently invent a confidence score; it must always trace back to either the original curated table or an explicit Gemini extraction with the source text attached.

## 10. Definition of done for v1

- AuraDB contains at least the original 22 gene-disease edges plus any newly extracted ones, fully matching the Section 6 schema
- Live Cloudflare Pages site queries Neo4j through the Cloudflare Pages Function — verified with dev tools that no credentials leak client-side
- `python curator/run_pipeline.py` can be run repeatedly without creating duplicate nodes (idempotency verified)
- README documents how to add a new dataset end-to-end in under 10 steps
