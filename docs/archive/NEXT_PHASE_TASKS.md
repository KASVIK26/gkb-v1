# AgriHub-KB — Next Phase Task Plan
**Generated:** 2026-07-05  
**Based on:** Full codebase audit against `PROJECT.md` phase checklist

---

## Current State Summary

Phases 0–3 and 6–7 are substantially complete. The core skeleton works: the seed data can be loaded into AuraDB, the Cloudflare Pages Function queries Neo4j over HTTPS, and the frontend fetches and renders edges. What is missing is the **AI extraction pipeline** (Phase 4), a handful of **critical bugs** that block the pipeline from running at all, and the **live deployment** (Phase 8).

| Phase | Status | Notes |
|---|---|---|
| 0 — Repo & account setup | ✅ Done | Wrangler, .env.example, git in place |
| 1 — Schema & empty graph | ✅ Done | `schema.py`, `init_constraints.py`, `db.py` |
| 2 — Seed load | ✅ Done | 22 edges in `seed_data.py`, `setup.py` orchestrates it |
| 3 — GFF3 parser | ✅ Done | `gff_parser.py`, `assembly_parser.py`, `genomic_integration.py` |
| 4 — AI extraction | ❌ Not started | `paper_extractor.py` raises `NotImplementedError` |
| 5 — Validation layer | ⚠️ Partial | Field-level validation exists; duplicate/orphan checks missing |
| 6 — API layer | ✅ Done | `query.js` + `varieties.js` using HTTPS Query API |
| 7 — Frontend | ✅ Done | `app.js` fetches live; loading states wired |
| 8 — Deploy & verify | ❌ Not done | No Cloudflare Pages secrets configured, not live |
| 9 — Growth loop | ❌ Blocked | Blocked by Phase 4 and pipeline bugs |

---

## Cluster A — Fix Critical Pipeline Bugs

These must be resolved before the pipeline can run end-to-end. They are quick fixes but are currently blockers.

### A1 — Fix the `ModuleNotFoundError: No module named 'curator'`
**Priority:** Critical  
**File:** `curator/run_pipeline.py`, project root

The pipeline crashes immediately when run directly with `python curator/run_pipeline.py` because Python cannot find the `curator` package. The `README.md` already shows the correct fix (`$env:PYTHONPATH="c:\Users\vikas\gkb-v1"`), but it is easy to miss. The permanent fix is to add a minimal `pyproject.toml` (or `setup.cfg`) so the package can be installed as editable with `pip install -e .`. This means any invocation — pytest, direct script run, IDE — finds the package without manually setting `PYTHONPATH`.

**Acceptance:** `python curator/run_pipeline.py` runs without import errors when invoked from the project root, without setting `PYTHONPATH` first.

---

### A2 — Handle chickpea dataset format (GBFF ≠ GFF3)
**Priority:** High  
**File:** `config/datasets.yaml`, `curator/run_pipeline.py`

The chickpea entry (`chickpea_icc4958`) in `datasets.yaml` points to a `.gbff.gz` file (GenBank flat-file format). The pipeline's `process_dataset()` function checks for `.gff.gz`/`.gff3.gz` extensions and silently returns `"Not GFF3 format"` for the chickpea dataset — so it is marked `downloaded` but never actually processed.

Two options (choose one):
1. **Replace the file reference** — Download the chickpea GFF3 annotation from NCBI instead of the GBFF, update `local_path` and `type` in `datasets.yaml`. The NCBI accession GCA_000347275.4 has a GFF3 annotation available.
2. **Add a GenBank parser** at `curator/parsers/gbff_parser.py` that extracts gene IDs and coordinates from GBFF format and integrate it into `run_pipeline.py`'s dispatch logic.

Option 1 is faster. Option 2 is more general if you plan to add more GBFF-only sources later.

**Acceptance:** Running the pipeline with the chickpea dataset marked `downloaded` produces a non-zero `genes_parsed` count and no "Not GFF3 format" error.

---

### A3 — Implement dataset status update after successful load
**Priority:** Medium  
**File:** `curator/run_pipeline.py`

`PROJECT.md` specifies that after a dataset is successfully loaded, `run_pipeline.py` must flip its `status` from `downloaded` to `loaded` in `datasets.yaml`. This is not implemented. Without it, every pipeline run re-processes every downloaded dataset from scratch, which breaks idempotency at the registry level (even if the Neo4j MERGEs are safe).

Add a `update_dataset_status(dataset_id, new_status, registry_path)` helper that reads `datasets.yaml`, finds the matching entry by `id`, updates its `status`, and writes the file back. Call it at the end of `process_dataset()` on success.

**Acceptance:** After a successful pipeline run, the processed dataset's `status` in `datasets.yaml` reads `loaded`. Re-running the pipeline skips it.

---

### A4 — Add soybean chromosome mapping
**Priority:** Low  
**File:** `config/datasets.yaml`

The wheat and chickpea datasets have `assembly_report` keys pointing to NCBI assembly report files, which `genomic_integration.py` uses to translate sequence accession IDs into human-readable chromosome labels (1A, Ca1, etc.). The soybean entry has no `assembly_report` key, so soybean gene coordinates will be stored with raw accession IDs instead of chromosome labels like Gm01, Gm02.

Download the soybean WM82 assembly report from NCBI (GCA_002905335) into `data/raw/` and add the `assembly_report` path to the soybean entry in `datasets.yaml`.

**Acceptance:** After a pipeline run for soybean, `Gene.chromosome` values are labels like `Gm01`, not `CM008980.2`.

---

## Cluster B — AI Extraction Pipeline (Phase 4)

This is the highest-value missing piece. It is what makes the knowledge base actually grow beyond the original 22 seed edges.

### B1 — Implement `paper_extractor.py` with Gemini API
**Priority:** Critical  
**File:** `curator/extractors/paper_extractor.py`

The file currently contains a single stub function that raises `NotImplementedError`. Implement `extract_paper_text(text: str, api_key: str) -> dict` to:

1. Call the Gemini API (`gemini-2.5-flash` or `gemini-flash-lite`) with a system prompt that forces JSON-only output.
2. The system prompt must enumerate the exact field list from `PROJECT.md` Section 6 schema: `gene`, `disease`, `pathogen`, `resistance_type`, `varieties`, `confidence`, `iot_trigger`, `treatment`, `source`.
3. Parse the JSON response and return a dict that matches that schema.
4. Validate `confidence` is one of `Very High`, `High`, `Medium` before returning — reject/flag anything outside that enum.

Install dependency: `google-generativeai` (already in requirements.txt if not, add it).

**Acceptance:** Given a real wheat stem rust paper abstract, `extract_paper_text(abstract, api_key)` returns a dict with all required fields populated and valid `confidence`.

---

### B2 — Add retry/backoff for Gemini 429 errors
**Priority:** High  
**File:** `curator/extractors/paper_extractor.py`

The Gemini free tier is rate-limited (~10–15 RPM). Batch runs over multiple papers will hit 429s without retry logic. Implement exponential backoff: on a 429 response, wait 2^attempt seconds (cap at 60s), retry up to 5 times before raising.

Use Python's `time.sleep()` directly — no external retry library needed.

**Acceptance:** Manually triggering a 429 condition (e.g., running in a tight loop) shows the extractor sleeping and retrying rather than crashing.

---

### B3 — Implement `review_queue.json` and human-approval flow
**Priority:** High  
**File:** `curator/extractors/paper_extractor.py`, `curator/run_pipeline.py`

`PROJECT.md` is explicit that extracted records must go through a human review step before reaching `loader.py`. After B1 is implemented, extracted records should be written to `data/review_queue.json` (appended, not overwritten). A separate CLI command — `python curator/approve_extractions.py` — should display each pending record, prompt `[a]pprove / [s]kip / [e]dit`, and move approved records to `data/approved_queue.json` for loading.

The `run_pipeline.py` orchestrator should not call `loader.py` directly on freshly extracted records — it should write to `review_queue.json` and then stop, telling the user to run the approval step.

**Acceptance:** Running the extraction step populates `review_queue.json`. Running the approval script allows approving a record, after which it moves to `approved_queue.json`. Running the pipeline again loads only approved records.

---

### B4 — Run extraction on 5–10 real papers
**Priority:** Medium  
**File:** `data/` (paper excerpts), `curator/extractors/`

Once B1–B3 are working, manually curate abstracts from 5–10 real papers covering wheat stem/stripe/leaf rust, soybean sudden death, or chickpea ascochyta blight. Save each excerpt as a plain `.txt` in `data/papers/` (gitignored if they're large), run extraction, approve the records, and verify they load into AuraDB as new nodes/edges beyond the 22 seed entries.

**Acceptance:** AuraDB node/relationship count increases beyond the 22-edge baseline after running extraction + approval + load for at least 5 papers.

---

## Cluster C — Enhanced Validation (Phase 5 completion)

### C1 — Add duplicate edge detection to `validator.py`
**Priority:** High  
**File:** `curator/validator.py`

The existing validator only checks field-level conformance on a single record. Add `validate_no_duplicate_edge(record: dict, existing_edges: list[dict]) -> None` that checks whether a `(gene, disease, source)` triple already exists in the records being loaded in the same pipeline run. Duplicate edges from the *same source* should be rejected; duplicate edges from *different sources* can coexist (they are independent observations).

**Acceptance:** If two records in the same run share the same gene, disease, and source, `validate_no_duplicate_edge` raises `ValidationError`.

---

### C2 — Add orphan node detection
**Priority:** Medium  
**File:** `curator/validator.py`

After loading, a `Variety` node that has no `CARRIES` relationships (i.e., no genes) is likely a data error. Add a post-load check `check_orphan_nodes(driver: DBDriver) -> list[str]` that queries AuraDB for any `Variety` nodes with no outgoing `CARRIES` edges and returns their names. Log a warning but don't abort (they may be intentional placeholders).

**Acceptance:** The function returns a (possibly empty) list of orphaned variety names when called after a load operation.

---

### C3 — Write unvalidated records to `review_queue.json` instead of crashing
**Priority:** Medium  
**File:** `curator/validator.py`, `curator/run_pipeline.py`

Currently, validation failures raise `ValidationError` and crash the pipeline. Instead, catch `ValidationError` in `run_pipeline.py`, append the failing record + the error message to `data/review_queue.json`, and continue processing the rest of the batch. Only hard-fail on schema-level errors (missing required fields) — soft-fail on confidence enum mismatches and duplicates so a single bad record doesn't block a 50-record batch.

**Acceptance:** A batch with one bad confidence value does not crash the pipeline; the bad record appears in `review_queue.json` and the rest load successfully.

---

## Cluster D — Deploy & Verify Live Site (Phase 8)

### D1 — Configure Cloudflare Pages environment secrets
**Priority:** High  
**Prerequisites:** AuraDB instance must have the 22 seed edges loaded (setup.py run locally first)

In the Cloudflare Pages dashboard for this project, add environment variables under Settings → Environment Variables → Production:
- `NEO4J_URI` — the `neo4j+s://...` Aura URI
- `NEO4J_USER` — `neo4j`
- `NEO4J_PASSWORD` — the Aura password
- `NEO4J_DATABASE` — the database name (derived from URI if left blank)

Do **not** put these in `wrangler.toml` or any committed file.

**Acceptance:** The Pages Function returns real data when called via the deployed URL.

---

### D2 — Push to GitHub and trigger Cloudflare auto-deploy
**Priority:** High  
**Prerequisites:** D1

Commit all current working files (minus `.env`) and push to the `master` branch. Cloudflare Pages should trigger a build and deploy automatically. Verify the deploy log shows no errors.

**Acceptance:** The Cloudflare Pages deploy log shows a green build. The live site URL loads.

---

### D3 — End-to-end live verification (no credential leaks)
**Priority:** Critical (this is the "definition of done" for v1)

1. Open the live site URL in a browser.
2. Select **Wheat** → **Chinese Spring** → click Search.
3. Verify 3 resistance edges are returned (Sr33, Yr18, Lr34 or equivalent).
4. Open browser dev tools → Network tab → inspect the `/api/query` request and response.
5. Confirm: no `NEO4J_URI`, `NEO4J_USER`, or `NEO4J_PASSWORD` appears anywhere in the request headers, response body, or any other network call.

**Acceptance:** Steps 1–5 all pass. Screenshot or note the result for the README.

---

## Cluster E — Frontend Polish

### E1 — Add IoT trigger toggle filter
**Priority:** Medium  
**File:** `public/index.html`, `public/app.js`

`PROJECT.md` (Section 7) mentions an "optional IoT toggle" in the UI. The API already returns `iotTrigger` data per edge but the current `index.html` has no toggle. Add a checkbox "Show IoT-triggered treatments only" that filters the rendered edge cards client-side to only show edges where `iotTrigger` is non-null.

**Acceptance:** Toggling the checkbox filters edge cards in real time without re-querying the API.

---

### E2 — Show pathogen and source in edge cards
**Priority:** Low  
**File:** `public/app.js`

The `renderEdges()` function in `app.js` references `edge.gene`, `edge.disease`, `edge.chromosome`, `edge.allele`, `edge.confidence`, `edge.resistanceType`, and `edge.treatment` — but `edge.pathogen` and `edge.source` are returned by the API yet not displayed. Add them to the card template.

**Acceptance:** Each rendered edge card shows the pathogen name (e.g., *Puccinia graminis* f.sp. *tritici*) and the data source string.

---

### E3 — Add a knowledge base stats bar
**Priority:** Low  
**File:** `public/index.html`, `public/app.js`, `functions/api/`

Add a small `/api/stats` Cloudflare Pages Function that returns node/relationship counts from AuraDB:
```json
{ "crops": 3, "varieties": N, "genes": N, "diseases": N, "edges": N }
```
Display these counts as a compact bar at the top of the page (e.g., "22 resistance edges · 3 crops · 12 diseases"). Refresh on page load only.

**Acceptance:** The stats bar shows accurate counts matching AuraDB Browser.

---

## Cluster F — CI / Testing Hygiene

### F1 — Add GitHub Actions workflow for pytest
**Priority:** Medium  
**File:** `.github/workflows/test.yml` (new file)

Create a minimal GitHub Actions workflow that runs `pytest tests/ -q` on every push to `master`. The workflow should install Python 3.11, install requirements, and run tests. Tests that require a live Neo4j connection should be gated behind a `@pytest.mark.integration` marker so they are skipped in CI (where no AuraDB credentials are available) but can be run locally.

**Acceptance:** Pushing to `master` triggers the Actions workflow. Unit tests pass. Integration tests are skipped (not failed) in the CI environment.

---

### F2 — Expand `test_pipeline.py` coverage
**Priority:** Medium  
**File:** `tests/test_pipeline.py`

The current `test_pipeline.py` is a near-empty placeholder. Add tests for:
- `load_dataset_registry()` with a mock YAML file
- `select_downloaded_datasets()` with mixed-status entries
- `process_dataset()` with a non-GFF file (should return "Not GFF3 format" error without crashing)
- `update_dataset_status()` (once A3 is implemented)

Use `tmp_path` (pytest fixture) for temporary YAML files. No Neo4j connection needed for any of these.

**Acceptance:** `pytest tests/test_pipeline.py -v` passes with at least 6 test cases.

---

### F3 — Add tests for `paper_extractor.py` with mocked Gemini
**Priority:** Medium  
**File:** `tests/test_paper_extractor.py` (new file)  
**Prerequisites:** B1

Add unit tests that mock the Gemini HTTP call (use `unittest.mock.patch`) and verify:
- A well-formed response produces the correct schema dict
- A response with an invalid `confidence` value raises `ValidationError`
- A 429 response triggers retry with backoff (mock `time.sleep` and verify it is called)
- A response that is not valid JSON raises a clear error

**Acceptance:** All tests pass without a real Gemini API key.

---

## Cluster G — Growth Loop Infrastructure (Phase 9)

### G1 — Add `scripts/add_dataset.py` utility
**Priority:** Low  
**File:** `scripts/add_dataset.py` (new file)

The `scripts/` directory is empty. Add a small CLI script that prompts for dataset metadata (id, crop, type, local_path, source) and appends a new entry to `config/datasets.yaml` with `status: not_downloaded`. This removes the need to manually edit YAML for each new dataset and reduces the chance of formatting errors.

**Acceptance:** Running `python scripts/add_dataset.py` creates a valid new entry in `datasets.yaml`.

---

### G2 — Source and add 2+ new datasets to the registry
**Priority:** Low  
**Prerequisites:** A1, A2

Once the pipeline reliably processes the existing three datasets, identify and register at least two more:
- A wheat cultivar panel VCF (e.g., from the IWGSC wheat pangenome project) for SNP-level resistance data
- A chickpea GFF3 annotation if the GBFF issue in A2 is resolved via replacement rather than a new parser
- Any soybean disease resistance QTL dataset from SoyBase

Update `config/datasets.yaml` and document the download procedure in the README.

**Acceptance:** `datasets.yaml` contains at least 5 entries with clear `source` and `local_path` fields.

---

## Recommended Execution Order

1. **A1** (fix import bug) — unblocks everything else in the pipeline
2. **A2** (chickpea format) — unblocks the chickpea dataset
3. **A3** (status update) — completes idempotency promise
4. **B1 → B2 → B3** (Gemini extractor) — the core value-add; do these together in one session
5. **C1 → C3** (validation improvements) — can run in parallel with B
6. **D1 → D2 → D3** (deploy) — once you have at least the seed data loaded and want a live URL
7. **E1 → E2** (frontend polish) — after D3, once real data is flowing
8. **F1 → F3** (CI/tests) — ongoing, add as each cluster lands
9. **B4, G1, G2** (growth loop) — ongoing after v1 is declared done

---

## Definition of Done for v1 (from PROJECT.md)

- [ ] AuraDB contains the original 22 seed edges plus ≥5 newly extracted edges, all matching Section 6 schema
- [ ] Live Cloudflare Pages site queries Neo4j through the Pages Function
- [ ] Browser dev tools confirm no credentials leak client-side
- [ ] `python curator/run_pipeline.py` is idempotent (verified by running it twice and checking node counts did not increase on second run)
- [ ] README documents how to add a new dataset end-to-end in under 10 steps
