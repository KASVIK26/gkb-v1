# Review log: pathotype prevalence, release tables, 2023-24 rust, soybean report reactions (2026-10-04)

**Reviewer: Claude (an AI), acting for the project owner.** No reviewer name or `status: reviewed`. Parser-made evidence (`parser:...`) has no model in it; evidence from the
candidate route (`llm:`) stays discounted. All new quotes were re-checked against the live documents (exact).

## 1. Pathotype prevalence by state (68 claims, tier A)
`batches/make_pathotype_prevalence.py` reads the state-wise pathotype distribution tables of wheat stripe rust and stem rust in the AICRP Crop Protection reports 2020-21 to 2022-23.
A row is used only if its pathotype counts add up to the isolates the report prints; `frequency_pct` = count / isolates (derived; the quote is the row); `years` = end year of the crop season.
New: 12 pathotypes (Pst 110S84, 47S103, 46S103, 79S68, 0S0, 6S0, 7S0; Pgt 21, 34-1, 40A, 40-2, 40-3) and nine state zones. Includes the central-India rows (MP: Pgt 11 in 86 % of 28 isolates in 2022;
MH: Pgt 11 in 53 % of 17 isolates in 2023). Not read: leaf-rust tables (2021-22 drops its empty cells so columns cannot be aligned; 2022-23's header is one column short), 2020-21's stem table (counts do not add up).

## 2. Wheat releases and identified varieties (89 claims, 24 new varieties)
Release / identification tables of the Director's reports 2020-21, 2022-23 and 2025-26 (the 2021-22 and 2023-24 reports could not be read: damaged PDFs). `batches/make_wo16.py` cuts each row
out of the report text; each claim quotes the row. Central and Peninsular zone releases (plus the Indore-bred NWPZ ones): zone and production condition, and the rust reactions the "special features" column states
(resistant / highly resistant -> R, "tolerant" -> MR, "moderately resistant" -> MR). Interleaved columns in the PDF mean a phrase is accepted when its words occur in order; the quote is always the contiguous row.
2025-26 entries are "identified", not yet notified: no release year is recorded. Comparative statements ("better resistance than the recurrent parent") are not used.

## 3. AICRP 2023-24 rust tables (121 claims) and parser fixes
The 2023-24 report was not read before because its captions read "table: 1.2." (with a colon). Fixed in `aicrp_rust.py` (tests added): the colon, stem rust marked (S) and stripe rust (N) in the header, the elite
nursery header ("entry rusts lb kb pm ... stem leaf leaf stripe") and a multi-year guard that now sees "2021-2022, 2022-23, and 2023-24" (Table 1.4 stays unread). 2 of 896 pairs have ACI above the printed
severity (ACI 62.2 at 60 %): neither entry is a KB variety. More seasons mean more variety-season contradictions: the conflict flag count is now 179 (tier capped at C where flagged).

## 4. Soybean reactions from the AICRP on Soybean reports (21 claims, 27 evidence rows)
The ICAR-NSRI site publishes the AICRP on Soybean annual reports 2017-18 to 2024-25 (open). Their plant-pathology narrative states "entries X, Y showed HR / AR / MR reaction to <disease> at <centre>" and
"the variety DSb 21 maintained HR reaction to rust for the last nine years". Seven reports were read for sentences that name the disease and a KB variety (`batches/make_wo17.py`):
rust (DSb 21 across six sources: tier A; DSb 23; MACS 1188), charcoal rot (JS 20-34, JS 20-98, JS 21-72, NRC 130/150/181, MACS 1520, AMS 100-39), frogeye leaf spot (JS 20-116, JS 20-34, NRC 150, RSC 11-07, PS 1347),
anthracnose pod blight "PB(CT)" (AMS-MB-5-18, MACS 1520, NRC 127, NRC 128). Absolute and high resistance both map to R. Sentences that do not name the disease, rows of per-centre matrices (empty cells are dropped by the
PDF so columns cannot be aligned), yellow mosaic virus and Rhizoctonia aerial blight (not in scope) were left out.

## Not done
- The per-entry matrices (PP3 tables) of the soybean reports; the 2024-25 / 2025-26 wheat reports (password-protected); leaf-rust pathotype tables.
