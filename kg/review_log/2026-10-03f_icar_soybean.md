# Review log: ICAR-IISR Indore soybean files (2026-10-03)

**Reviewer: Claude (an AI), acting for the project owner.** The folder `icar_soybean_files/` (1.7 GB, gitignored, never committed) holds two GBS genotype files (Gmax v6.0) and two
sample sheets from an ICAR-IISR scientist. **No phenotype data is in them**, so nothing about resistance can be concluded from the genotypes alone; the useful output is a quality
report for the scientist and the science of the paper behind the panel.

## Added to the graph
`kg/curated/soybean_charcoal_rot_gwas_v1.yaml` (script `make_gwas_charcoal_rot.py`; 42 evidence rows, all exact against the live paper; parser-made, so no model discount):
- **18 QTL_ASSOCIATION claims** (soybean charcoal rot, first QTLs for it in the KB; before: 0), one per SNP of Tables 6 (glasshouse, seedling) and 7 (3-year sick plot, adult), with the
  Williams 82 (Wm82.a2.v1) position, the most significant p-value printed for the SNP and the number of field years. GWAS evidence weight 0.60 -> tier C. Most loci are "suggestive"
  in the paper's own classification (p between 1e-4 and the Bonferroni cutoff 7.46e-7); S14_51754926 (p 1.3e-9, adult) and S14_50857981 (seedling), 1 Mb apart, are the authors' headline.
- **22 QTL_CONTAINS_REFGENE claims**: the defence-related genes the authors list within 200 kb of the loci (Table 8), as RefGene entities in the KB's own soybean annotation
  (Wm82.gnm6.ann1): the Glyma ids survive from a2 to v6 and each gene was kept only if its v6 model has the paper's length (+-10 %) or sits where the length-matching genes of the same
  chromosome put it (within 100 kb of their a2->v6 offset). 22 of 23 passed; Glyma.18G239700 is not in v6 and is not asserted. Includes the NB-ARC genes near S14_50857981.
- **2 VARIETY_REACTION claims**: JS 95-60 and JS 93-05 susceptible to charcoal rot in three sick-plot years (the paper's own statement about its checks).
- Not added: the "top 10" genotype lists (a ranking, not a reaction class); PI 159923 "resistant" (an accession); JS 20-76 and EC 602288 "resistant" (names a genotype, not shown to be a released variety).
- Paper typo noted: the Results text says S14_51718686 where the abstract and Table 7 say S14_51754926; only the table value is used.

## Findings about the data (for the scientist; `icar_soybean_files/derived/QC_REPORT_for_ICAR_IISR.md`, not committed)
64 of 395 libraries are >= 90 % missing in the raw calls yet carry imputed genotypes; 22 of 27 same-name sample pairs are far apart genetically (labels or lots); median heterozygosity
5.5 %. Several of the charcoal-rot paper's best genotypes (MACS 1520, Young, Bragg, NRC 2396, AMS MB 100-39) are among the failed libraries. 23 of the 69 soybean varieties in the KB
are in the panel. **No variety-gene or haplotype claim was made from these files**: with failed libraries, doubtful labels and no phenotypes it would be a guess presented as data.

## What would unlock more
The phenotype sheets for the 395, a re-run without the failed libraries, and the plate map (see section 4 of the QC report). Then: association in v6 coordinates, haplotypes at the
published loci for the 23 released varieties in the panel, and variety -> locus claims with evidence.
