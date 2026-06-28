# AgriHub Genomic Knowledge Base

Initial scaffold for the AgriHub knowledge base project.

## What is in place

- Canonical graph schema constants in `curator/schema.py`
- Neo4j load and constraint entrypoints in `curator/loader.py` and `curator/init_constraints.py`
- Pipeline placeholder in `curator/run_pipeline.py`
- Validation helpers in `curator/validator.py`
- **Assembly report parser** in `curator/parsers/assembly_parser.py` — maps NCBI sequence IDs to human-readable chromosome labels (e.g., Chr1A → 1A, Ca_LG1 → Ca1)
- **Genomic integration layer** in `curator/parsers/genomic_integration.py` — loads chromosome mappings and translates gene coordinates
- **Dataset registry** in `config/datasets.yaml` — links assembly reports to their corresponding GFF/FASTA files

## Next steps

1. **Parse GFF3 with chromosome mapping** — Implement `curator/parsers/gff_parser.py` to extract genes using `gffutils` and map sequence IDs to human-readable chromosome labels via assembly reports.
2. **Implement Gemini extraction** — Wire `curator/extractors/paper_extractor.py` to extract gene-disease relationships from paper text.
3. **Frontend integration** — Update `public/app.js` to handle loading state and display real data from the API (already mostly done, just needs small tweaks).
4. **Deploy to Cloudflare Pages** — Push to GitHub and deploy via Cloudflare Pages (auto-deploy on push).
5. **End-to-end testing** — Verify that the live site queries real data from Neo4j with no credential leaks.

## Local setup

1. Copy `.env.example` to `.env` in the repo root.
2. Fill in `NEO4J_URI`, `NEO4J_USER`, and `NEO4J_PASSWORD` from your AuraDB instance.
3. Set `NEO4J_DATABASE` to your AuraDB database name. If you leave it blank for an Aura URI like `neo4j+s://<database>.databases.neo4j.io`, the Pages Function derives it from the hostname.
4. Add your `GEMINI_API_KEY` from Google AI Studio.
5. Keep `.env` out of git; it is already ignored.
6. Download the three raw genomic files into `data/raw/` using the paths in `config/datasets.yaml`.
7. Change each dataset `status` from `not_downloaded` to `downloaded` once the file is present.
8. Run `$env:PYTHONPATH="c:\Users\vikas\gkb-v1"; C:/Python314/python.exe curator/setup.py` to initialize constraints and load 22 seed edges.
9. Run `C:/Python314/python.exe -m pytest tests/ -q` to verify all tests pass.

## Database initialization

Once `.env` is filled in, run the setup script:

```powershell
$env:PYTHONPATH="c:\Users\vikas\gkb-v1"
C:/Python314/python.exe curator/setup.py
```

This will:
1. Create uniqueness constraints in Neo4j (Gene.id, Variety.name+crop, Disease.name)
2. Load 22 seed gene-disease edges covering wheat, soybean, and chickpea
3. Verify the connection and report success

## API layer status

The `/api/query` endpoint (in `functions/api/query.js`) is now wired to query Neo4j:
- Uses Neo4j's HTTPS Query API for Cloudflare Workers compatibility (avoids Bolt driver sockets)
- Accepts the standard Aura `neo4j+s://...` URI and converts it to the HTTPS Query API endpoint internally
- Uses `NEO4J_DATABASE` when present, otherwise derives the database name from Aura hostnames like `<database>.databases.neo4j.io`
- Returns edges in the shape expected by the frontend
- Supports both `__all__` (all varieties) and specific variety queries

Run the Pages app locally with:

```powershell
npx -y wrangler pages dev public
```

## Dataset registry

The first three datasets are already registered in `config/datasets.yaml`:

- wheat IWGSC gene annotation GFF3 (with assembly report)
- soybean WM82 v6 FASTA
- chickpea ICC4958 FASTA (with assembly report)

When those files are downloaded, the pipeline will pick them up automatically after you flip their status to `downloaded`.

### Assembly reports: critical for human-readable gene coordinates

The project includes **NCBI assembly reports** for wheat and chickpea:
- `data/raw/GCF_018294505.1_IWGSC_CS_RefSeq_v2.1_assembly_report.txt` (wheat)
- `data/raw/GCA_000347275.4_ASM34727v4_assembly_report.txt` (chickpea)

These files map **sequence accessions** (GenBank/RefSeq IDs used in GFF files) to **human-readable chromosome labels** (1A, 1B, 1D for wheat; Ca1, Ca2, Ca3 for chickpea). Without them, gene coordinates stay locked to internal sequence identifiers.

The integration layer (`curator/parsers/genomic_integration.py`) loads these mappings and translates gene chromosome IDs, so when a gene is stored in Neo4j, its chromosome property is human-readable and traceable back to NCBI.
