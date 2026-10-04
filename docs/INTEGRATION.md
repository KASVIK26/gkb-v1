# Integration guide: how the other AgriHub products use the knowledge graph

Replaces the superseded sections 2-4 of `interfaces.md` (written when the IoT readings were assumed to live in this repo's database; they do not). Written 2026-10-04.

The GKB **answers questions and hands over knowledge**; it never calls the other products and stores no sensor readings, device logs or farmer data. Each of the four products keeps its
own deployment and database; they meet only through the identifiers and the read API below.

## 1. What the GKB gives each product

| Product | Reads | Why |
|---|---|---|
| (a) Phenomics model (Lightning AI) | `/api/features?variety_id=` ; disease ids from the crosswalk | A numeric prior per disease (susceptibility of the variety, whether it is known, the evidence tier, resistance genes carried) to fuse with the image classifier's probabilities, and the label vocabulary |
| (b) IoT device (own Supabase project) | `kg_disease_triggers` view / `/api/profile?type=disease` ; sensor variable names in `config/vocab/sensors.yaml` | The cited weather conditions that favour each disease (variable, bounds, aggregation, window, crop-stage range), plus the advisory to show |
| (d) Mobile app and researcher dashboard | `/api/profile`, `/api/query`, `/api/varieties`, `/api/evidence`, `/api/graph` | A variety's reactions, genes and zones; a disease's resistant varieties, genes, loci, triggers, advisories and pathotype survey; the evidence behind each statement |
| Yield model | `/api/features` | Resistance vector and zone indicators as features |

## 2. Identifiers (stable)

`kg/ids_crosswalk.tsv` (generated: `agrihub kg publish-files`) lists every disease, variety, gene, zone and pathogen with its KG id, names, synonyms and the abbreviations the reports use,
plus **empty columns for the label each other product uses** (`phenomic_model_label`, `iot_label`, `mobile_app_label`): the owners of those products fill them in; nothing is guessed here.
Rules: `docs/DATA_DICTIONARY.md`. Disease ids (`dis:<crop>:<slug>`) are frozen by `config/vocab/diseases.yaml`; variety ids are `var:<crop>:<normalised name>`; a claim id is a hash of its content,
so the same statement has the same id in every release, and an id never changes meaning.

## 3. The read API (Cloudflare Pages functions; all GET unless noted; JSON)

| Endpoint | Returns |
|---|---|
| `/api/stats` | counts of crops, varieties, genes and QTLs, diseases, claims |
| `/api/varieties?crop=wheat` | `[{id, name}]` |
| `/api/profile?type=variety|disease|gene&crop=wheat&list=1` | the entities to choose from |
| `/api/profile?type=variety|disease|gene&id=<kg id>` | one profile: every statement with its tier, score, source count and conflict flag |
| `/api/features?variety_id=<id>` | numeric feature vector (below) |
| `/api/query` (POST `{crop, variety}`) | crop-wide gene claims, QTLs, and for a variety its reactions and genes |
| `/api/evidence?claim_id=claim:<hex>` | the sources behind a claim (title, year, venue, link, kind of evidence, locator); verbatim quotes stay in the database for audit |
| `/api/graph` | all nodes and edges, for visualisation |
| `/api/triggers` (POST) | **demo only**: single-snapshot check of typed sensor values against the trigger library; not the risk engine |

The same data is available as Postgres views in the `public` schema of the GKB Supabase project (`kg_*`), read-only for the `anon` role.

## 4. Meaning of confidence (read this before using a claim)

Every claim has `score` (0-1), `tier` (A >= 0.85, B >= 0.65, C >= 0.40, D below) and `conflict` (true when readings for the same variety and disease disagree; capped at C). Tiers come from the evidence
method, the number of independent sources, a x0.6 factor for model-found evidence not yet reviewed by a person, and a x0.8 factor for old evidence on race-structured diseases.
**No claim has yet been reviewed by a person** (`human_reviewed` is false everywhere). `docs/QC_REPORT.md` shows how far the tiers move when these constants change; treat the tier as a ranking, not a probability.

## 5. Feature vector (`/api/features`)

One block per disease of the variety's crop, plus variety-level entries:

| Feature | Meaning |
|---|---|
| `<disease>.susceptibility` | 1.0 (S/HS), 0.7 (MS), 0.35 (MR), 0.1 (R) from the best-supported reading (highest tier, then most sources); `null` when no reading exists |
| `<disease>.known` | 1 when a reading exists, else 0 (an unknown is never guessed) |
| `<disease>.tier_weight` | A 1.0, B 0.75, C 0.5, D 0.25 of that reading; 0 when unknown |
| `<disease>.conflict` | 1 when readings of this variety for this disease disagree |
| `<disease>.n_resistance_genes_carried` | recorded genes of the variety that are known to act on this disease |
| `n_genes_carried`, `release_year`, `zone.<CODE>` | gene count, release year (or null), 1 for each zone the variety is recommended for |

The response also carries the scale tables so a model can reuse or replace them. Version `"1"`.

## 6. The planned risk endpoint (not built)

`POST /api/risk` is designed in `docs/risk_engine_design.md` (parked by owner decision, 2026-10-03): it must work with whichever sensors a field has, compute each trigger condition over its own
window, gate by crop stage, combine with the variety's reaction and the surveyed pathotype share, and return the matched and unmatched conditions with their evidence. The GKB side of its inputs now exists:
triggers (17 claims), reactions, genes, and pathotype prevalence by state (`kg_disease_profile.pathotype_prevalence`). The engine itself, back-testing and the contract tests with the IoT team remain open.

## 7. Versions and stability

Each build is a release schema `kg_<yyyy_mm_n>`; `agrihub kg promote` repoints `kg_current` atomically, and the `public` views follow. `kg/manifest.json` records the release, counts, git SHA and checksums.
A consumer should log the release tag it read (`kg/metadata.jsonld`), and may pin an older release by reading its schema directly. Releases are reversible (`kg promote --release <older>`).
