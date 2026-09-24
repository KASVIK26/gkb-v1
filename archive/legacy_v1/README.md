# Legacy v1 seed (archived 2026-09-25)

`seed_data.py` holds the original 22 "curated" edges. **Do not load them.** Many rows are
factually wrong (chromosomes, crop, gene names, variety carriers, invented confidence).
See RESEARCH_ROADMAP.md §2.2 D3 for the error list. Useful rows are re-curated with
citations in Phase 3 (task 3.8) into `kg/curated/seed_v2.tsv`.

`seed_loader.py` and `setup.py` were the Neo4j loaders for this seed and are kept for reference only.
