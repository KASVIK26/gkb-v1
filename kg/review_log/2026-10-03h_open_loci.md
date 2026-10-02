# Review log: soybean / chickpea resistance loci from open-access papers (2026-10-03)

**Reviewer: Claude (an AI), acting for the project owner.** No reviewer name or `status: reviewed`. Locus claims are parser-made (no model, full weight of their evidence method);
the Rpp gene claims are `llm:` (discounted).

## How it was done
Europe PMC was searched by title for each empty disease; open-access mapping papers were read and their tables parsed by `batches/make_open_loci.py`. Each locus is one table row; each claim
quotes the header and that row. Assembly and position are stored only where the paper states the assembly. Names are made unique per paper (e.g. `SMV-SC3_4_7299944`) so that numbered SNP ids from
different studies cannot collide. All 83 locus evidence rows were re-checked against the live papers (exact); the 7 Rpp gene claims were verified at ingest.

## Added (QTL panel and gene panel)
| Disease | New | Source |
|---|---|---|
| Soybean rust | 7 loci (Uganda GWAS, 312 accessions: 6; qSBR18.1 in Chiang Mai 5: 1) + Rpp1-b, Rpp5, Rpp6 as genes (Rpp1-4 gained a source: Rpp1 now tier A) | pmid:42122877, 36672760, 37375888 |
| Soybean mosaic virus | 19 GWAS loci (strains SC3: 14, SC7: 5); the Chr13 ~29-31 Mb loci sit in the Rsv1 region | pmid:40604369, 41963778 |
| Frogeye leaf spot | 4 GWAS SNPs + 19 RIL QTL (largest: qFLSm-18-1, LOD 23.8, 18.9 % of variation) | pmid:34895144, 42199232 |
| Bacterial pustule | 2 loci on chromosomes 6 and 18, different from the classical rxp on chromosome 17 | pmid:39273969 |
| Chickpea Fusarium wilt | 32 single-study QTLs (races 0-5; includes the Indian C214 x WR315 and JG62 x WR315 populations) | pmid:40050693 (review table, so evidence is a review statement) |

## Judgement calls
- Study populations are Chinese, Brazilian, Ugandan, Thai and Indian; they are crop-level loci and say nothing about an Indian variety. Most GWAS hits are near the significance threshold (the panel shows the p-value).
- The SMV paper prints some positions in rounded scientific notation; positions are taken from the SNP id, which carries the full number.
- Frogeye RIL: for QTL measured in several environments the highest LOD row is used.
- Uganda rust GWAS: the stage is left "unspecified" (natural infection, rust index); only the paper's stated assembly (Wm82.a4.v1) is recorded.
- Seven soybean-rust-adjacent and frogeye papers from the same groups (race 7 mapping, pod-and-stem-blight, etc.) were not parsed: overlapping loci or not in scope.

## Not found (the honest gaps)
- **Chickpea dry root rot, collar rot and rust**: no open-access QTL, GWAS or gene-mapping paper turned up in Europe PMC (title and full-text searches). Resistance there is reported as germplasm screening only.
- **Soybean anthracnose, pod and stem blight, Rhizoctonia root rot**: no open mapping paper (the one anthracnose study is a screen; the Phomopsis seed decay and stem-canker papers are other diseases).
  Charcoal rot is covered by the 18 loci added earlier.
