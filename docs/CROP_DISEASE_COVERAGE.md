# Crop × disease coverage (release 2026_10_36, 2026-10-04)

What the knowledge graph currently holds for each of the 17 in-scope diseases. "Resistant/susceptible varieties" counts distinct varieties with at least one reading of that kind (a variety can appear in
both columns if sources disagree). "Genes" and "QTL loci" are distinct gene-disease and locus-disease claims. Full detail, including evidence and tiers, is in the dashboard's Profiles tab; the numbers
behind this table are in `docs/QC_REPORT.md`.

| Crop | Disease | Resistant varieties | Susceptible varieties | Genes | QTL loci | Weather triggers | Advisories | Pathogen linked |
|---|---|---|---|---|---|---|---|---|
| Wheat (129 varieties) | Stem rust | 70 | 22 | 22 | 0 | 1 | 4 | yes |
| Wheat | Leaf rust | 82 | 17 | 16 | 17 | 1 | 5 | yes |
| Wheat | Stripe rust | 25 | 36 | 11 | 9 | 1 | 5 | yes |
| Wheat | Powdery mildew | 0 | 0 | 46 | 39 | 1 | 3 | yes |
| Wheat | Fusarium head blight | 0 | 0 | 7 | 19 | 1 | 1 | yes |
| Soybean (69 varieties) | Charcoal rot | 18 | 2 | 0 | 18 | 1 | 1 | yes |
| Soybean | Soybean rust | 5 | 2 | 8 | 7 | 2 | 2 | yes |
| Soybean | Soybean mosaic | 4 | 0 | 3 | 19 | 0 | 2 | yes |
| Soybean | Frogeye leaf spot | 6 | 0 | 1 | 23 | 1 | 1 | yes |
| Soybean | Bacterial pustule | 11 | 0 | 1 | 2 | 1 | 1 | yes |
| Soybean | Anthracnose (pod blight) | 6 | 0 | 0 | 0 | 1 | 3 | yes |
| Soybean | Pod and stem blight | 0 | 0 | 0 | 0 | 1 | 1 | yes |
| Soybean | Rhizoctonia root rot | 0 | 0 | 0 | 0 | 1 | 1 | yes |
| Chickpea (47 varieties) | Fusarium wilt | 41 | 0 | 8 | 40 | 2 | 2 | yes |
| Chickpea | Dry root rot | 12 | 0 | 0 | 2 | 1 | 2 | yes |
| Chickpea | Collar rot | 5 | 0 | 0 | 0 | 1 | 1 | yes |
| Chickpea | Chickpea rust | 0 | 0 | 1 | 0 | 0 | 3 | yes |

## Reading it

- **Wheat is the strongest crop across the board**: every rust has reaction data, genes, and (except stem rust) QTLs; powdery mildew and FHB are gene/QTL-rich but have no variety-level reaction yet.
- **Soybean is uneven**: charcoal rot, mosaic and frogeye now have real loci (added this week), but anthracnose, pod and stem blight, and Rhizoctonia root rot have reaction data at best and no genetic data.
- **Chickpea is lopsided toward Fusarium wilt** (41 resistant varieties, 8 genes, 40 QTLs — the best-covered disease in the whole graph) while the other three diseases are thin. Collar rot has no genetic data
  at all; chickpea rust has reaction data for no variety.
- **Zero susceptible readings for several diseases** (powdery mildew, FHB, mosaic, frogeye, anthracnose, Rhizoctonia, pod/stem blight, collar rot, chickpea rust) usually means the data we hold is one-sided —
  mostly resistance screens and gene/QTL papers that don't report susceptible checks by name, not that the disease has no susceptible varieties in reality.
- **Every disease has its pathogen identified** and at least one weather trigger except soybean mosaic (no trigger: it's vector-borne, not weather-driven in the same way) and chickpea rust (no trigger yet).
