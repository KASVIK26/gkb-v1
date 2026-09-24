# AgriHub-KB — Future Vision

This document extends the PROJECT.md constraints and describes what the knowledge base
can grow into beyond v1. It is a planning document for the next phases of the project.

---

## The Core Problem with v1 (Honest Assessment)

The v1 template seed is a **proof-of-concept graph**, not a production-ready agricultural
knowledge base. Its limitations are structural:

| Limitation | Current State | Why It Matters |
|---|---|---|
| Varieties per crop | 1 (Chinese Spring, Williams 82, ICC4958) | Farmers grow 100s of local varieties; 1 variety is useless for crop-specific queries |
| Resistance genes | 22 curated seed genes | India has 300+ characterized resistance loci across three crops |
| Disease types | 6 diseases total | Each crop faces 10–15 economically significant diseases in India |
| Geographic specificity | None | Punjab wheat vs Madhya Pradesh wheat face completely different disease pressures |
| Data freshness | Static | New pathotype virulence data comes out annually from ICAR/NBPGR |

**The graph only becomes worthwhile when it has enough variety-gene-disease connections to answer real questions like:**
> "What resistance genes does variety HD3086 carry, and are they still effective against the Ug99 lineage stem rust races currently in India?"

That requires at minimum 20–30 varieties per crop, 50–100 genes per crop, and annual updates.

---

## Phase 10 — More Varieties (Immediate Priority)

**Goal:** Reach 20+ varieties per crop in Neo4j. This is what makes the frontend useful.

### Wheat — India Priority Varieties
Add these as Variety nodes with `BELONGS_TO` Wheat and `CARRIES` gene edges:

| Variety | Released | Diseases (priority genes) |
|---|---|---|
| HD2781 (Raj 4120) | 2011 | Stem rust (Sr2, Sr38), Leaf rust (Lr28, Lr24) |
| HD3086 (Pusa Wheat 3086) | 2015 | Leaf rust (Lr28, Lr3ka), Stripe rust (Yr27, Yr59) |
| GW322 | 2011 | Stripe rust (Yr34, Yr27), Powdery mildew (Pm genes) |
| NW1014 | 2015 | Leaf rust, Stem rust (pyramided MABC) |
| K307 | 2009 | Stem rust (Sr24, Sr31) |
| WH711 | 2004 | Leaf rust (Lr28), Stem rust |
| DBW17 | 2005 | Stripe rust (Yr genes), Leaf rust |
| PBW502 | 2006 | Multiple rust (pyramided) |
| Raj4120 | 2014 | Stem rust (Sr38), Leaf rust |
| HI8498 | 2012 | Drought + leaf rust |
| MACS6222 | 2012 | Stem rust, Maharashtra zone |
| Shatabdi (WB2) | 2004 | Stripe rust, Eastern India |
| K9107 | 2009 | Leaf rust, UP eastern zone |
| DBW303 | 2023 | Multi-rust (new release) |
| Karan Aman (DBW187) | 2020 | Stem/Leaf rust, NEPZ |
| HD2967 | 2011 | Leaf/Stripe rust (widely grown) |
| PBW343 | 1995 | Susceptible (historical benchmark) |
| Lok1 | 1969 | Susceptible (historical) |
| NI5439 | — | Stem rust differential |
| WL711 | — | Leaf rust differential |

### Soybean — India Priority Varieties
| Variety | State/Zone | Diseases (priority genes) |
|---|---|---|
| JS 335 | MP, MH | Charcoal rot, Phytophthora |
| JS 9305 | MP, MH | Rust (Rpp-like), FLS |
| MAUS 81 | Maharashtra | Phytophthora (Rps1c), Yellow mosaic |
| MAUS 612 | Vidarbha | Charcoal rot tolerant |
| DSb21 | AP | Phytophthora |
| NRC7 | National | Rhizoctonia root rot |
| NRC37 | National | Phytophthora, MV virus |
| RKS18 | Rajasthan | Drought + charcoal rot |
| PS1347 | Punjab | SDS-tolerant |
| BRAGG | — | Cyst nematode resistance (Rhg1) |
| Williams 82 | — | Reference genome (already in v1) |
| PI 88788 | — | SCN (Rhg1 source) |
| Hartwig | — | SCN (Rhg4 source) |
| Clark | — | FLS (Rcs3 source) |

### Chickpea — India Priority Varieties
| Variety | Type | Diseases (priority genes) |
|---|---|---|
| JG 11 | Desi | Fusarium wilt race 1-4 |
| JG 14 | Desi | Fusarium wilt, Ascochyta |
| JG 74 | Desi | FW (became susceptible to race 4) |
| Pusa 256 | Desi | FW, BGM tolerant |
| Pusa 372 | Desi | FW, AB moderate resistance |
| Pusa 391 | Desi | FW (became susceptible — see Pusa Chickpea 20211) |
| Pusa Chickpea 20211 | Desi | FW races 1-5 pyramided (released 2022) |
| KAK 2 | Kabuli | FW, AB moderately resistant |
| Phule G 12013 | Desi | FW, Maharashtra region |
| GNG 1958 | Desi | FW, Rajasthan |
| ICC4958 | Desi | Reference genome (already in v1) |
| ICCV 2 | Kabuli | BGM moderately resistant |
| ICCV 96030 | Desi | AB, FW both resistant |
| GPF2 | Desi | Ascochyta blight (AB QTL donor) |
| ICC506EB | Desi | BGM resistance source |
| ILWC292 (C. reticulatum) | Wild | BGM, AB resistance donor |

---

## Phase 11 — Expand Resistance Gene Catalog

Currently 22 seed genes. Target: 100+ genes across 3 crops.

### Wheat additions (priority)
`Lr34`, `Lr46`, `Lr67`, `Yr18`, `Yr29`, `Yr46`, `Sr2`, `Sr24`, `Sr25`, `Sr31`,
`Sr33`, `Sr35`, `Sr36`, `Sr38`, `Sr45`, `Sr50`, `Pm41`, `Pm46`, `Fhb1`, `Fhb2`,
`Fhb4`, `Fhb5`, `Yr81`, `Lr28`, `Lr3ka`, `Lr16`, `Lr24`, `Lr26`, `Lr57`, `Lr68`

### Soybean additions (priority)
`Rps1a`, `Rps1b`, `Rps1c`, `Rps1d`, `Rps1k`, `Rps3a`, `Rps6`, `Rps8`,
`Rhg1`, `Rhg4`, `Rpp1`, `Rpp2`, `Rpp3`, `Rpp4`, `Rpp5`, `Rpp6`,
`Rcs3`, `Rxp`, `Rmd`, `Rfi1`, `Rmi1`, `Rmi2`

### Chickpea additions (priority)
`foc1-QTL-CaLG02`, `foc4-QTL-CaLG04`, `foc5-SNP-block-Ca2`,
`AB-QTL-GPF2-LG3`, `BGM-QTL-ICCV2-LG6`, `DRR-QTL-CaLG03`,
`collar-rot-GWAS-locus-Ca4`, `Phytophthora-QTL-CaLG7`

---

## Phase 12 — Paper Pipeline at Scale

The `scripts/fetch_papers.py` tool (already built) covers 63 curated PMC papers.
Scale-up plan:

1. **PubMed search automation** — replace the static curated list with dynamic PubMed API
   searches (`esearch.fcgi`) using MeSH terms:
   - wheat AND ("rust resistance"[MeSH]) AND India AND ("2020/01/01"[PDAT] : "3000"[PDAT])
   - soybean AND (Phytophthora OR "cyst nematode") AND (gene OR QTL OR marker)

2. **Full-text extraction** — current OAI-PMH approach gets full XML; add a cleaner
   that strips tables/references and keeps only abstract + results + conclusion (~2000 tokens)
   to stay within Gemini free-tier context limits.

3. **Structured Paper node** — add `Paper` to the graph schema:
   ```
   (Gene)-[:REPORTED_IN]->(Paper {pmid, pmcid, year, title, doi})
   ```
   This enables provenance queries: "which papers report Sr33?" and citation-count
   weighting of confidence scores.

4. **Auto-discovery mode** — weekly cron (GitHub Actions) that runs the search,
   fetches new papers, extracts, and adds to `review_queue.json`. You review once a week.

---

## Phase 13 — Geographic / Agro-Ecological Zones

Add geographic metadata to disease pressure data:

```
(Disease {name, pathogen})-[:PREVALENT_IN]->(AgroZone {zone, states, crops})
(Gene)-[:EFFECTIVE_AGAINST {zone, year_tested}]->(Disease)
```

India agro-zones for this project:
- **NWPZ** — Punjab, Haryana, HP, Jammu (wheat dominant)
- **NEPZ** — UP, Bihar, Jharkhand, West Bengal (wheat + soybean)
- **CZ** — MP, Chhattisgarh (wheat + soybean + chickpea)
- **PZ** — Maharashtra, Gujarat, AP (soybean + chickpea)
- **NE** — Assam, Meghalaya (soybean, rust risk)

Frontend change: add a zone dropdown so farmers can filter by their location.

---

## Phase 14 — QTL / SNP Layer

Current graph has only gene names (`Sr33`). Add coordinate-linked QTL nodes:

```
(Gene {id: "Sr33", chromosome: "1D", start: ..., end: ...})
(QTL {name: "foc-CaLG02", chromosome: "Ca2", peak_marker: "STMS11",
      lod: 12.4, r2: 0.68, linked_gene: "foc-resistance-1"})
(Variety)-[:HAS_QTL {effect: 0.68, environment: "Indore-2022"}]->(QTL)
```

Data source: GFF3 coordinates already parsed by the genome pipeline (Phase 3, already done).
QTL meta-data from the papers fetched in Phase 12.

---

## Phase 15 — Pathotype / Race Tracking

Current graph has `Disease.pathogen` as a string. Expand:

```
(Disease)-[:CAUSED_BY]->(Pathotype {race, virulence_formula, year_detected, zone})
(Gene)-[:EFFECTIVE_AGAINST {tested_year}]->(Pathotype)
```

**Why this matters:** Stem rust gene Sr31 was effective until Ug99 broke it in 2000.
A gene that worked in 2010 may not work now. The graph should track:
- When a gene became ineffective (pathotype evolution)
- Which India-detected races have broken which genes
- Current recommended gene combinations

Data sources: Annual ICAR/NBPGR rust nursery reports, USDA cereal disease lab bulletins.

---

## Phase 16 — IoT Sensor Integration (existing partial)

Current `Treatment.iot_trigger` is a text string (`"humidity > 80%"`).
Expand to a proper sensor-linked alert system:

```
(Treatment)-[:TRIGGERED_BY]->(SensorThreshold {
    metric: "relative_humidity",
    threshold: 80,
    unit: "%",
    duration_hours: 6,
    disease: "Ascochyta Blight"
})
```

API endpoint addition:
```
POST /api/sensor-alert
Body: { crop, zone, sensor_readings: { humidity: 85, temp: 18, leaf_wetness: 1 } }
Response: { alerts: [{ disease, gene_breakdown, treatment, confidence }] }
```

Hardware integration:
- ESP32 + DHT22 sensor → MQTT → Cloudflare Worker → alert push
- Low-cost sensor kit (~₹500) uploadable to the same AuraDB

---

## Phase 17 — Multi-Language Support

India has 22 official languages. For the KB to reach farmers:
- Add Hindi translations of disease names and treatments
- Add Marathi/Gujarati/Telugu for regional varieties
- Partner with ICAR state centers for vernacular disease name mapping

Schema addition: `{name_hi, name_mr, name_te}` on Disease and Treatment nodes.

---

## Phase 18 — API Expansion & Multi-Country

Current API: `POST /api/query` (crop + variety → edges).
Expand:

| Endpoint | Purpose |
|---|---|
| `GET /api/crop/:crop/varieties` | All varieties for a crop |
| `GET /api/gene/:id` | Full gene profile (diseases, varieties, papers, zones) |
| `GET /api/disease/:name/genes` | All genes effective against a disease |
| `POST /api/sensor-alert` | IoT-driven disease alert |
| `GET /api/search?q=Sr33` | Full-text node search |
| `GET /api/stats` | Live graph statistics |

Multi-country: same schema works for Bangladesh (wheat), Nepal (wheat/soybean),
and Sri Lanka (soybean). CIMMYT and ICRISAT data covers these geographies already.

---

## Cost & Scale Reality Check

| Component | v1 (current) | v2 target | v3 target |
|---|---|---|---|
| Neo4j AuraDB nodes | 64 | ~2,000 | ~20,000 |
| Resistance gene edges | 22 | ~500 | ~5,000 |
| Papers processed | 0 | 63 (curated) | 500+ (automated) |
| Varieties | 3 | ~60 | ~300 |
| AuraDB quota used | 0.1% | ~4% | ~40% |
| Cost | $0 | $0 | $0 (still free tier) |

The AuraDB free tier (50K nodes, 175K relationships) is sufficient through v3.
No infrastructure cost increase until 300+ varieties with full coordinate data.

---

## Recommended Next Actions (Ordered)

1. **Add 20 wheat varieties** using existing seed_loader.py — 2 hours work
2. **Add 15 soybean varieties** — 1 hour
3. **Add 15 chickpea varieties** — 1 hour
4. **Run `python scripts/fetch_papers.py --all --no-extract`** to cache all 63 papers locally
5. **Get Gemini API key** and run `python scripts/fetch_papers.py --extract-only` to fill review_queue.json
6. **Review and approve** extractions via `python curator/approve_extractions.py`
7. **Download chickpea GFF3** from LegumeInfo (see below) and re-run the pipeline
8. **Add geographic zone data** to Disease nodes (Phase 13)

---

## Chickpea GFF3 Download (Action Required)

The GBFF file from NCBI has no gene features. Use this instead:

**LegumeInfo ICC4958 GFF3 (desi, gnm2.ann1):**
```
Base URL: https://data.legumeinfo.org/Cicer/arietinum/annotations/ICC4958.gnm2.ann1.LCVX/
```

Expected file: `cicar.ICC4958.gnm2.ann1.LCVX.gene_models_main.gff3.gz`

Steps:
```bash
# 1. Browse to confirm filename
# https://data.legumeinfo.org/Cicer/arietinum/annotations/ICC4958.gnm2.ann1.LCVX/

# 2. Download
curl -L -o data/raw/cicar.ICC4958.gnm2.ann1.LCVX.gene_models_main.gff3.gz \
  "https://data.legumeinfo.org/Cicer/arietinum/annotations/ICC4958.gnm2.ann1.LCVX/cicar.ICC4958.gnm2.ann1.LCVX.gene_models_main.gff3.gz"

# 3. Update config/datasets.yaml (see below) and run:
python -m curator.run_pipeline
```

Then update `config/datasets.yaml`:
```yaml
- id: chickpea_icc4958_gff3
  crop: chickpea
  type: gene_annotation
  local_path: data/raw/cicar.ICC4958.gnm2.ann1.LCVX.gene_models_main.gff3.gz
  source: "LegumeInfo — Cicer arietinum ICC4958, gnm2.ann1.LCVX (desi type)"
  status: downloaded
```

Gene ID format in this GFF3 will be: `cicar.ICC4958.gnm2.ann1.Ca_NNNNN`
Chromosomes: Ca1–Ca8 (8 linkage groups = all chromosomes)

---

## Summary

v1 is a working pipeline with a correct schema and a live Neo4j graph.
It is not yet a useful agricultural tool — it has too few varieties and genes.

The path to usefulness:
1. More varieties (manual seed loader additions — 1 day)
2. More genes from papers (fetch_papers.py + Gemini — 1 day)
3. Geographic zone metadata (half day)
4. Annual updates (30 minutes/update with the pipeline)

The infrastructure is already correct. The bottleneck is now data volume, not code.
