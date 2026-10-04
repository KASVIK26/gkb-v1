# Review log: wheat GWAS loci, profiles, QC, analytics, publication files (2026-10-04)

**Reviewer: Claude (an AI), acting for the project owner.** No reviewer name or `status: reviewed`. Locus claims are parser-made; every quote re-checked against the live paper (126 exact in `loci_open_papers_v1.yaml`).

## Added to the graph: 43 wheat loci
`batches/make_open_loci.py` now also reads two wheat papers:
- **Leaf rust and stripe rust in Indian advanced breeding lines** (pmid:41882545, BLINK multi-locus GWAS, three seasons): 17 leaf-rust and 7 stripe-rust marker-trait associations, with the best p-value, the variance
  explained and the number of seasons in which each appeared. Before this the graph held no leaf-rust QTL and two stripe-rust QTLs. Chromosome only: the paper cites two RefSeq versions, so no position is recorded.
- **Fusarium head blight in CIMMYT and South Asian germplasm** (pmid:40430810, 174 genotypes, three years): 19 marker-trait associations (the paper's MLMM table), best p-value per SNP. Wheat FHB had 7 genes and no QTL.
Left out: Yr27 and Yr2KS gene -> disease links (no open paper states them as a sentence we can quote; the Indian GWAS only places a marker near "Yr27/Lr13").

## Fix found by the new QC report
`HI 8849` was given the synonym "Pusa Mangal", which already names `HI 8713` (released 2013): two varieties cannot share a synonym. Removed. Two other name collisions are real and harmless: `Purna` names both
AKW 1071 and HI 1544 (an ambiguous name is rejected by the resolver, never guessed), and MAUS 612 / Pratishta (MAUS 61-2) are pinned by id.

## New code (all tested)
- **Profiles** tab and `/api/profile`, `/api/features` (views `kg_variety_profile`, `kg_disease_profile`, `kg_gene_profile`): a page per variety, disease or gene with the tier and evidence of every statement; the feature vector never guesses an unknown reaction.
- **`agrihub kg qc`** (`docs/QC_REPORT.md`): provenance integrity, tiers, coverage per crop and disease, structure checks, distance to the roadmap targets, and a sensitivity analysis: model-evidence discount, staleness factor, evidence weights +-20 %,
  tier cut-offs +-0.05. Finding: the tiers are sensitive to the evidence weights (+-20 % moves 30-47 % of claims) and to the model-evidence discount (17-21 %); read the tier as a ranking.
- **`agrihub kg analytics`** (`docs/ANALYTICS.md`): wheat varieties resistant to all three rusts, observed susceptibility, rust-gene deployment by zone, dominant pathotypes by state and season, recommended varieties with unrecorded readings.
- **`agrihub kg publish-files`**: the ID crosswalk for the other products (their label columns are left empty on purpose), the data dictionary from the models, dataset metadata. Plus `docs/INTEGRATION.md`, `CITATION.cff`, `CHANGELOG.md`.
  The licence is not set: it is the owner's decision.
