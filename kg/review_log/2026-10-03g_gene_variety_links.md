# Review log: gene -> variety links, a third AICRP report, QTL display (2026-10-03)

**Reviewer: Claude (an AI), acting for the project owner.** No reviewer name or `status: reviewed`; model-found evidence stays `llm:` (discounted); parser-made evidence has no model in it.

## What was added
1. **AICRP Crop Protection report 2020-21** (the only older report the site publishes; `Crop-Protection-Report-2020-21-Compressed-1.pdf`):
   - postulation tables (Sr/Lr/Yr genes in AVT entries) read by `aicrp_postulation.py`: 63 rows, 2 skipped because the names did not add up to the printed count;
   - rust reactions read by `aicrp_rust.py` (Tables 1.2, 1.5, 9.1, 9.2): 175 claims, ACI never exceeds the highest severity (0 violations in 1,394 pairs).
   - **Bug found and fixed**: Table 1.4 prints one row per year (2018-19, 2019-20, 2020-21 plus a mean) under each entry; the parser read it as one season with shifted columns (28 wrong claims). The parser now skips any table whose caption names several seasons (test added).
   - Postulation claims now cover three reports: 134 variety-gene claims, 86 postulated in at least two reports; HI 1634 (Yr9 in two reports, Yr2 in the third) and MP 4010 (Yr2 vs Yr9) have their Yr genes withheld.
2. **IARI leaf-rust gene table** (pmid:40678044, 86 genotypes): only 4 of the 86 are varieties the KB has (PBW 299, UP 262, HUW 510, MP 4010), 6 claims. The rest (WL 711, WH 291, HUW 213, PBW 120 ...) are not in the KB's variety list.
3. **HI 1500 carries Lr24** (pmid:36352858, donor parent in a marker-assisted backcross) and **Lr14a -> leaf rust** (the IARI table's own heading), 2 claims, quotes exact.
4. **Genome regions (QTL) are now shown** in the Browse tab: a new `kg_qtl_associations` view (position, p-value or LOD, markers, study population, genes in the region) and a panel grouped by disease.

Verification: 421 + 7 + 2 new evidence rows, all exact against the live documents.

## Not done, and why
- **2024-25 and 2025-26 Crop Protection reports** are on the site but password-protected PDFs (they do not open with an empty password). Not read; a copy from IIWBR would unlock two more seasons of gene postulations and reactions.
- **2023-24 report** has only a summary of the gene postulation (class-level sentences, no per-entry tables), so no variety-gene claims.
- Yr27 and Yr2ks (carried by 2 and 7 varieties, source: the review table) still have no gene -> disease claim.
- Wheat varieties with a gene: 61 -> 65 of 105. The 40 still without one are central-India varieties (HI, MACS, UAS, NIAW, AKAW, DWR, MP ...) that the published gene tables do not list.
