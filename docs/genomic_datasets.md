# Genomic datasets: survey and recommendation

**Date:** 2026-09-26 · **Question asked:** which additional genomic datasets should we download, searched extensively across wheat/soybean/chickpea, covering the 17 in-scope diseases.

## The recommendation, up front

**Don't download any of these now. Revisit when Phase 4 (genomic layer) actually starts.**

What's already in `data/raw/` — the three reference genome annotations (IWGSC CS RefSeq v2.1 for wheat, Wm82.gnm6 for soybean, ICC4958.gnm2.ann1 for chickpea) — is **sufficient for everything currently planned**: identifying NLR/resistance-gene candidates from annotation, and anchoring genes/QTLs to physical coordinates (Phase 4 tasks 4.1–4.5). Every dataset below adds value for a *later* need — mainly variety-level haplotyping, which needs the variety list from Phase 3 to even be useful — not the current one. Downloading them now would repeat the exact mistake already found and fixed in this project: the 752 MB chickpea GBFF that sat unused because nothing needed it yet.

The one exception worth flagging: **PRGdb** (below) is small (a downloadable annotation file, not a genome) and could reasonably be pulled in whenever Phase 4's NLR-candidate work starts, to cross-check the in-house domain-based classifier against an independent source. Still not urgent.

## What's already in hand (Phase 0–1, unchanged)

| Crop | File | Registered in |
|---|---|---|
| Wheat | IWGSC CS RefSeq v2.1 genome + GFF + assembly report | `config/datasets.yaml` |
| Soybean | Wm82.gnm6.ann1 GFF3 | `config/datasets.yaml` |
| Chickpea | ICC4958.gnm2.ann1.LCVX GFF3 + assembly report | `config/datasets.yaml` |

## What exists, for when it's actually needed

### 1. Pangenomes / multiple reference assemblies (haplotype diversity beyond one cultivar)

| Crop | Dataset | Where | Notes |
|---|---|---|---|
| Wheat | **10+ Wheat Genomes Project** — 10 chromosome-level + 5 scaffold-level assemblies (Walkowiak et al. 2020, *Nature*, [PMID 33239791](https://pubmed.ncbi.nlm.nih.gov/33239791/)) | [10wheatgenomes.com](https://10wheatgenomes.com/), [wheatgenome.info](https://wheatgenome.info/wheat_genome_databases.php), also on EnsemblPlants | Captures structural variation across breeding programs; useful once specific varieties beyond Chinese Spring need haplotyping |
| Soybean | **Pan-genome of wild and cultivated soybeans** — 26 accessions (Liu et al. 2020, *Cell*, [PMID 32553274](https://pubmed.ncbi.nlm.nih.gov/32553274/)) | [SoyBase Glycine Pan-Genome page](https://legacy.soybase.org/PanGenome/PanGenome.php) | 3 wild, 9 landrace, 14 cultivar; presence/absence and copy-number variant calls already computed |
| Chickpea | No dedicated multi-assembly pangenome found distinct from the resequencing set below (see §2) | — | The 3,366-genome resequencing project effectively serves this role for chickpea |

### 2. Large genotyping / resequencing panels (connects *varieties*, not just the reference cultivar, to known gene/QTL regions — the actual prerequisite for `VARIETY_CARRIES_GENE` claims via haplotype, Phase 4)

| Crop | Dataset | Where | Notes |
|---|---|---|---|
| Soybean | **SoySNP50K** — ~42,509 SNPs across ~20,000 USDA germplasm accessions (18,484 *G. max*, 1,168 *G. soja*) (Song et al. 2013, [PMID 23372807](https://pubmed.ncbi.nlm.nih.gov/23372807/)) | [soybase.org/tools/snp50k](https://www.soybase.org/tools/snp50k/) — VCF available directly | The gold-standard soybean genotyping resource; almost certainly the first one to pull when Phase 4 needs soybean variety haplotypes |
| Wheat | **T3/Wheat (Triticeae Toolbox)** — SNP (including 90K Axiom), phenotype and pedigree data from US public breeding programs | [wheat.triticeaetoolbox.org](https://wheat.triticeaetoolbox.org/) (free account required) | US-centric, not Indian material, but the array design and pipeline are directly reusable if/when Indian wheat SNP data is found |
| Chickpea | **CicerSeq** — 3,366 genomes (3,171 cultivated + 195 wild) resequenced (Varshney et al. 2021, *Nature*, DOI [10.1038/s41586-021-04066-1](https://doi.org/10.1038/s41586-021-04066-1)) | [cegresources.icrisat.org/cicerseq](https://cegresources.icrisat.org/cicerseq/) — direct VCF download (`Chickpea_Pangenome.PAV.vcf.gz`), JBrowse genome browser, passport data | ICRISAT-hosted, the most directly useful of the three for this project given ICRISAT's Indian mandate |
| Chickpea | Earlier, smaller resequencing: 429 accessions from 45 countries (Varshney et al. 2019, *Nature Genetics*, [PMID 31036963](https://pubmed.ncbi.nlm.nih.gov/31036963/)) | Same CicerSeq portal | Superseded by the 3,366-genome set above; mentioned for completeness |

### 3. Trait/disease-reaction germplasm evaluation data (structured, Phase 7 territory)

| Source | What it has | Where |
|---|---|---|
| **USDA GRIN-Global** | Disease-reaction scores (descriptor data) for the full USDA soybean germplasm collection (~20,000 accessions) and other GRIN-held crops; ~50,000 new observation points/year across all crops | [ars-grin.gov](https://www.ars-grin.gov/) |
| **T3/Wheat** | Phenotype + pedigree data alongside the SNP data above | Same portal as §2 |

### 4. Resistance-gene reference databases (small, useful for cross-checking, not "download a genome")

| Database | What it is | Where |
|---|---|---|
| **PRGdb 4.0** — Plant Resistance Genes database | ~16,000 known/putative R-genes across 192 species; bulk annotation files per species; the DRAGO3 tool used to classify NLR/RLK/RLP candidates | [prgdb.org](http://prgdb.org) |

### 5. Pathogen genomes (relevant to 2+ of our 17 diseases each; lower priority — useful for Phase 12-style candidate-gene/effector work, not current phases)

| Pathogen | Relevant disease(s) | Where |
|---|---|---|
| *Puccinia graminis* f. sp. *tritici* | Wheat stem rust | [JGI MycoCosm — Pucgr1](https://mycocosm.jgi.doe.gov/Pucgr1) |
| *Puccinia triticina* | Wheat leaf rust | [JGI MycoCosm — Puctr1](https://mycocosm.jgi.doe.gov/Puctr1/Puctr1.home.html) |
| *Puccinia striiformis* f. sp. *tritici* | Wheat stripe rust | [JGI MycoCosm — Pucst1 / PST-78](https://mycocosm.jgi.doe.gov/Pucst_PST78_1/Pucst_PST78_1.home.html) |
| *Macrophomina phaseolina* | Soybean charcoal rot **and** chickpea dry root rot (the shared-pathogen link `docs/scope.md` calls out) | [Ensembl Fungi](https://jun2026-fungi.ensembl.org/Macrophomina_phaseolina_ms6_gca_000302655/Info/Index) |

## When to revisit this file

Trigger points, not a calendar date:
- **Phase 4 starts** (NLR candidate calling from the annotations already in hand) → check PRGdb for cross-validation.
- **A specific notified variety needs a resistance-gene call and no direct literature report exists** → that's when SoySNP50K / CicerSeq / T3-Wheat earn their download, for that variety specifically, not in bulk.
- **A pathotype-surveillance or candidate-avirulence-gene research question comes up** (Phase 12-adjacent) → pathogen genomes.

Until then, this file is the reference; nothing here needs to sit in `data/raw/`.
