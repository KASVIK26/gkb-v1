# Changelog of knowledge graph releases

Each release is a Postgres schema `kg_<tag>`; `agrihub kg promote` makes one live. Counts are claims. Details of every batch are in `kg/review_log/` and `PHASES.md`.
Reviews are AI first-pass reviews (no reviewer name, model-found evidence discounted); no claim has been reviewed by a person.

| Release | Claims | What changed |
|---|---|---|
| 2026_10_26 | 578 | AICRP rust parser (121 claims), chickpea/soybean reactions, zones and pedigree (WO01-WO03) |
| 2026_10_27 | 833 | Gene catalogue, variety-gene links, QTL meta-analyses (WO04-WO06) |
| 2026_10_28 | 869 | Rust pathotypes, fungicide recommendations and trials, soybean/chickpea reactions (WO07-WO11) |
| 2026_10_29 | 975 | AICRP gene-postulation reader: 106 variety-gene claims |
| 2026_10_30 | 983 | 20 gene -> disease links for rust genes; 12 duplicate gene edges removed; variety-specific gene panel |
| 2026_10_31 | 1025 | Soybean charcoal rot GWAS: 18 QTL loci, 22 candidate genes, 2 reactions |
| 2026_10_32 | 1231 | AICRP 2020-21 report (postulation + 175 rust reactions), IARI leaf-rust table, HI 1500 Lr24 |
| 2026_10_33 | 1317 | 83 soybean and chickpea QTL / GWAS loci from open papers; Rpp1-b, Rpp5, Rpp6 |
| 2026_10_34 | 1611 | Pathotype prevalence by state (68), wheat release tables (89, 24 varieties), AICRP 2023-24 rust (121), soybean AICRPS reactions (21) |
| 2026_10_35 | see `kg/manifest.json` | Wheat rust and Fusarium head blight GWAS loci (43), profiles, QC report, analytics, ID crosswalk |

Tooling added alongside: Crossref fallback for papers Europe PMC lacks, the outside-research verifier, parsers for the AICRP tables, the profile / features API, `kg qc`, `kg analytics`, `kg publish-files`.
