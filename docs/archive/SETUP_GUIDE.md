# AgriHub-KB — Step-by-Step Setup & Operations Guide

This guide covers every manual action needed to go from the current state
to a fully running, live system.  Follow the phases **in order**.

---

## PHASE 1 — Local Python Environment

### Step 1.1 — Install the package (fixes ModuleNotFoundError permanently)

Open a terminal in your project root (`C:\Users\vikas\gkb-v1`) and run:

```powershell
pip install -e ".[dev]"
```

This installs the `curator` package in editable mode plus all dependencies
including `neo4j`, `gffutils`, `google-generativeai`, `pytest`, `pytest-mock`.

**Verify:**
```powershell
python -c "import curator; print('OK')"
python -m pytest tests/ -q -m "not integration"
```
Expected: all unit tests pass (no integration tests are run without a DB).

---

### Step 1.2 — Check your .env file

Your `.env` at the project root must contain:

```
NEO4J_URI=neo4j+s://0db45a71.databases.neo4j.io
NEO4J_USER=0db45a71
NEO4J_PASSWORD=<your-password>
NEO4J_DATABASE=0db45a71
GEMINI_API_KEY=<your-gemini-key>
```

> ⚠ The `.env` file is gitignored.  **Never commit it.**

---

## PHASE 2 — Check Neo4j Graph Status

Run the status script to see what is currently in the database:

```powershell
python scripts/check_neo4j_status.py
```

This prints node counts, edge counts, all crops/diseases/varieties, sample
resistance edges, schema constraints, and AuraDB quota usage.

---

## PHASE 3 — Load Seed Data (if graph is empty)

If the status check shows 0 nodes, load the curated seed records first:

```powershell
python curator/seed_loader.py
```

This performs idempotent MERGE operations — safe to run multiple times.

**Verify:**
```powershell
python scripts/check_neo4j_status.py
```
You should now see Crops, Varieties, Genes, Diseases, and resistance edges.

---

## PHASE 4 — Run the Curator Pipeline (GFF3 data)

### Step 4.1 — Download the chickpea annotation (not yet downloaded)

The chickpea dataset has `status: not_downloaded` in `config/datasets.yaml`.

1. Go to: https://www.ncbi.nlm.nih.gov/datasets/genome/GCA_000347275.4/
2. Click **Download** → select **Genomic GFF**
3. Save the `.gff.gz` file as:
   `data/raw/GCA_000347275.4_ASM34727v4_genomic.gff.gz`
4. Also download the **Assembly report** (`.txt`) and save as:
   `data/raw/GCA_000347275.4_ASM34727v4_assembly_report.txt`
5. Edit `config/datasets.yaml` and change `status: not_downloaded` to `status: downloaded`

### Step 4.2 — Run the pipeline

```powershell
python -m curator.run_pipeline
```

The pipeline will:
- Skip chickpea if not downloaded
- Parse GFF3 for wheat and soybean
- Map raw sequence IDs to chromosome labels using assembly reports
- Load gene nodes into Neo4j
- Update `status` to `loaded` (or `error`) in `datasets.yaml`

---

## PHASE 5 — AI Paper Extraction (optional, adds resistance edges)

### Step 5.1 — Extract from a paper

```powershell
python curator/extractors/paper_extractor.py path/to/paper.txt --api-key $env:GEMINI_API_KEY
```

Replace `path/to/paper.txt` with a plain-text file (abstract or excerpt).
Extracted records are appended to `data/review_queue.json`.

### Step 5.2 — Human review and approval

```powershell
python curator/approve_extractions.py
```

Keys during review:
- `a` — approve and queue for loading
- `s` — skip (leave as pending)
- `e` — edit JSON inline before approving
- `q` — quit

Approved records go to `data/approved_queue.json`.

### Step 5.3 — Load approved records into Neo4j

```powershell
python curator/approve_extractions.py --load-only
```

---

## PHASE 6 — Cloudflare Pages Deployment

### Step 6.1 — Add encrypted environment secrets

1. Open https://dash.cloudflare.com → Pages → **agrihub-kb** (or your project name)
2. Go to **Settings → Environment Variables → Production**
3. Add the following as **Encrypted** variables:

   | Variable name    | Value                                    |
   |------------------|------------------------------------------|
   | `NEO4J_URI`      | `neo4j+s://0db45a71.databases.neo4j.io`  |
   | `NEO4J_USER`     | `0db45a71`                               |
   | `NEO4J_PASSWORD` | your AuraDB password                     |
   | `NEO4J_DATABASE` | `0db45a71`                               |

   > ⚠ Use **Encrypted** (not plain text).  These values are never visible after saving.

### Step 6.2 — Push to GitHub to trigger deployment

```powershell
cd C:\Users\vikas\gkb-v1
git add -A
git commit -m "feat: next-phase implementation — AI extraction, validation, frontend, CI"
git push origin main
```

Cloudflare Pages auto-deploys on every push to `main`.
GitHub Actions CI runs pytest in parallel (Python 3.11 + 3.12).

### Step 6.3 — Verify the live site

1. Open your Cloudflare Pages URL in a browser.
2. Open DevTools → **Network** tab.
3. Confirm:
   - `GET /api/stats` returns JSON with node counts.
   - POST to `/api/query` with `{"crop":"wheat"}` returns edges.
   - **No `NEO4J_` values appear anywhere in network traffic** (they must only exist server-side).
4. Check the stats bar renders at the top of the page.
5. Enable the **IoT Trigger** toggle — edges with `iot_trigger` should filter in/out.

---

## PHASE 7 — Add More Datasets (ongoing)

Use the interactive script to register a new dataset:

```powershell
python scripts/add_dataset.py
```

Follow the prompts.  After registering:
1. Download the file to the path you entered.
2. Set `status: downloaded` in `config/datasets.yaml`.
3. Re-run `python -m curator.run_pipeline`.

---

## Quick Reference — All Commands

```powershell
# Setup
pip install -e ".[dev]"

# Check DB status
python scripts/check_neo4j_status.py

# Load seed data
python curator/seed_loader.py

# Run GFF3 pipeline
python -m curator.run_pipeline

# Extract from paper
python curator/extractors/paper_extractor.py paper.txt

# Review extractions
python curator/approve_extractions.py

# Load approved records
python curator/approve_extractions.py --load-only

# Run unit tests
python -m pytest tests/ -q -m "not integration"

# Register new dataset
python scripts/add_dataset.py
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ModuleNotFoundError: No module named 'curator'` | Run `pip install -e ".[dev]"` in the project root |
| `NEO4J_URI is not set in .env` | Create/check `.env` file — see Step 1.2 |
| Pipeline says "Nothing to process" | Check `status: downloaded` in `config/datasets.yaml` |
| Gemini returns 429 | Rate limit hit — extractor retries automatically (up to 5×); wait a minute and retry |
| Cloudflare returns 503 "credentials not configured" | Add secrets in Cloudflare Pages dashboard (Phase 6.1) |
| Frontend shows no data | POST `/api/query` returns empty array — check DB has seed data loaded |
| `SHOW CONSTRAINTS` returns empty | Run `python curator/init_constraints.py` to create schema constraints |
