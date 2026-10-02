# Review log: AICRP gene-postulation reader (2026-10-03)

**Reviewer: Claude (an AI), acting for the project owner.** A crop scientist reviews the live graph. No reviewer name and no `status: reviewed` is written.
Unlike the work orders, nothing here was found by a language model: `curator/graph/aicrp_postulation.py` (command `agrihub kg import-aicrp-postulation`) reads the
report's own tables, so the evidence extractor is `parser:aicrp_postulation@1` and the x0.6 discount for model-found evidence does not apply.

## What it reads

Both AICRP Wheat & Barley Crop Protection reports already in the KB (2021-22 and 2022-23) print three tables, "Sr genes / Lr genes / Yr genes in AVT entries",
in which each row is a gene combination and the entries that carry it (`lr23+10+ 7 dbw173*, hpw349, mp3556, ...`). The genes are postulated by the IIWBR Regional
Station, Flowerdale (seedling tests with differential pathotypes; some Yr genes by linkage to an Lr/Sr gene). The report prints the number of entries in each row.

## Checks built into the reader

- **Counts:** every row's names must add up to the count the report prints; a row that does not is skipped, never guessed. Result: 134 rows, 0 skipped, and in all six tables
  the row counts also sum to the table's own "total" (Sr 93 / 133, Lr 100 / 113, Yr 78 / 94).
- **Only varieties the KB already has** become claims (the same policy as the rust-reaction reader): 33 varieties; about 220 AVT line names that are not released varieties are not Varieties.
- **Quotes:** each claim quotes the table caption and header and the whole row (a page header that falls inside a row is cut out and marked "..."). All 130 evidence rows verify against the live PDFs: 130 exact.

## Judgement calls

1. **Entries marked `*` ("different seed lot to that of previous cropping season") are not used.** The two years' postulations for such entries disagree
   (HD 3090: Sr31 + Lr26 + Yr9 in 2021-22, Lr13 + Lr10 + Yr2 in 2022-23), so which describes the variety is unknown. Nine KB varieties had a starred entry in some year
   (DBW 187, DBW 377, DDW 47, GW 322, GW 513, HD 3090, HI 1633, HI 1650, MP 4010); their unstarred rows are kept (GW 322 keeps Sr11 and Sr2, loses Yr9).
2. **HI 1634's Yr genes are withheld in both years** (Yr9 in 2021-22, Yr2 in 2022-23: neither contains the other; the 2022-23 report also lists it as resistant to brown rust only, which is
   not what Sr31 would give). Its Sr31 and Lr26 rows stand. NIAW 3170's Lr set differs only by an added Lr1 (nested), so both years are kept.
3. **Method:** claim method `postulation` (the table's column is called gene postulation), evidence method `postulation_pedigree` (weight 0.45): a lab inference, not a marker result.
   One claim per variety-gene pair, with one evidence row per report, so 24 of the 106 claims are postulated in both reports (two documents, tier B); the rest are tier C.
4. **Gene names:** `Yr18` resolves to the existing `Lr34` gene (synonyms in the KB); `Lr3` was missing and is created with only its symbol.
5. **Not merged with the review-table claims.** The 12 variety-gene pairs that the review table (pmid:33013989, work order WO05) also lists (HD 2967, HD 3086, GW 322) have a
   claim with method `stated` (tier D, 0.21) and now also one with method `postulation` (tier B or C). They are different claims because the method qualifier is part of a claim's
   identity; both are shown. Dropping the 12 `stated` duplicates is a one-line change if a single edge per pair is preferred.

## Known limits

- The reports list AVT entries tested that year; a variety that is not in the table for a year simply has no row for it. Absence is not a claim.
- Seedling-test postulation is an inference; Yr genes in particular are sometimes inferred from linkage. The tier says so (C, or B with two reports).
- Only the 2021-22 and 2022-23 reports exist in the KB; the same reader will read later reports of this layout.
- Names are as printed (`pb w871` was split by the PDF and read as `w871`, which is not a variety, so PBW 871 is missed).

The assembly script is in `kg/review_log/2026-10-03d/`.
