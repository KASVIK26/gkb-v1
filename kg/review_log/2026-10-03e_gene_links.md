# Review log: gene -> disease links, duplicate edges, variety-specific gene panel (2026-10-03)

**Reviewer: Claude (an AI), acting for the project owner.** No reviewer name or `status: reviewed`; `llm:` evidence stays discounted.

## Why
Of the 23 genes that varieties carry in the KG, 17 (Yr2 24 varieties, Lr13 21, Sr11 21, Lr23 13, Lr10 11, Sr7b 10, ...) had no gene -> disease claim, so
"HD 2967 carries Lr23" led nowhere. And the dashboard listed resistance genes crop-wide because it had no variety -> gene view.

## What changed
1. **WO13a, 20 new gene -> disease claims** (`kg/curated/rust_gene_links_v1.yaml`): Sr2/5/7a/7b/8a/8b/9b/9e/11/13/28/30 -> stem rust; Yr2, Yr9, Yra -> stripe rust;
   Lr1/3/10/13/23/24/28 -> leaf rust (and a second source for existing links). Source: the sentences in the 2021-22 and 2022-23 AICRP Crop Protection reports that name
   these as "stem rust resistance genes", "Yr genes ... contributed to yellow rust resistance", "Lr genes ... leaf rust resistance"; quotes copied from the report text,
   38 evidence rows, all exact against the live PDFs. Five candidates for pairs that already had a typed claim (Sr2, Sr24, Sr31, Lr26, Yr9) were dropped as vaguer.
   Resistance type stays `unknown` (the reports do not say all-stage or adult-plant). Not covered yet: Yr27, Yr2ks, Lr14a (carried by 1-7 varieties each).
2. **12 duplicate `stated` variety-gene claims removed** (GW 322, HD 2967, HD 3086): the AICRP postulation claims say the same, with better sourcing (`variety_gene_postulations_v1.yaml`).
3. **Dashboard gene panel is variety-specific** (`supabase/migrations/20261003000000_variety_gene_views.sql`, `functions/api/query.js`, `public/app.js`): choosing a variety shows the genes it
   carries, how that was established, the diseases each gene protects against, and the pathotypes that defeat it; a variety with no recorded gene says so ("nothing is known here, not that it carries none").

## Known limits
- Variety -> gene claims exist for wheat only (61 of 105 varieties). Soybean and chickpea have none; their gene -> disease coverage is the next work (see the table in the reply / PHASES item 48).
- The gene -> disease links are class-level statements (a gene named as a stem-rust gene); they carry no spectrum or effectiveness.
