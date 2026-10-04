# Finish plan (set 2026-10-04): what remains of the roadmap, in the order it is being done

Owner decisions: skip the ICAR Indore data (no update received), skip human review (the crop scientist reviews the live graph), finish as much as possible within the day.
Order = value to a credible knowledge graph first, then the pieces other products consume, then publication hygiene. Each step ends with tests, an audit of new quotes, a commit
and, at the checkpoints, a release (`kg load` + `kg promote`) and a dashboard deploy.

| # | Task | Roadmap phase | Why this position |
|---|---|---|---|
| 1 | Pathotype prevalence by state from the AICRP reports (stem, stripe, leaf rust distribution tables, 3 reports) | 8 / 12 inputs | 0 claims today; quick; the engine, gene-effectiveness and CQ3/CQ4 need it |
| 2 | Reaction volume: fix the 2023-24 report parser; find and parse AICRP soybean and chickpea reports; other open ICAR evaluation tables | 7 | Biggest gap: 472 of 3,000 reaction claims |
| 3 | Variety coverage toward 150 / 80 / 80 from official release lists | 3 | Needed for 2 and for gene links |
| 4 | Wheat gaps: Fusarium head blight loci and genes, Yr27 / Yr2ks gene links, remaining chickpea wilt genes | 3 / 4 | Closes the zero rows of the gene table that the literature can fill |
| 5 | Dashboard and API: variety profile, disease page, gene page; `/api/features` | 10 | Makes the data usable by the researcher dashboard |
| 6 | QC report and sensitivity analysis (`agrihub kg qc`) | 9 | Last open item of phase 9 without human review |
| 7 | Analytics: gene-deployment (weighted), knowledge-gap report, variety vulnerability inputs | 12 | Uses the gene, variety and pathotype data of steps 1-4 |
| 8 | Integration contracts and shared ID crosswalk; FAIR release metadata (license, citation, data dictionary, changelog) | 11 / 13 | Hand-over to the IoT, phenomics and mobile products; publication readiness |
| 9 | Refresh `PHASES.md`, final release, push, redeploy | all | Keeps the status honest |

## Not done on purpose (with the reason)
- **ICAR Indore genotype files:** no phenotypes or clean re-run received; QC report is ready for the scientist.
- **Human review:** the crop scientist reviews the live graph and sends corrections; the review-sheet workflow exists.
- **Risk engine (8.4), back-testing (8.3), IoT contract tests (8.5), phenomic/yield fusion (11.2-11.3):** parked at very low priority by the owner; design in `docs/risk_engine_design.md`.
- **Genome anchoring of markers (4.4) and NLR classification of wheat:** the wheat annotation has no domain data and BLAST anchoring is slow; not needed for the claims above.
- **Phase 5 corpus-scale extraction and phase 6 gold standard:** the verified outside-research route replaced the in-house LLM extraction; a 40-paper annotation set with a second annotator needs people.
- **Password-protected AICRP reports 2024-25 and 2025-26:** cannot be opened; a copy from IIWBR is needed.
- **Chickpea dry root rot / collar rot / rust and soybean anthracnose / pod and stem blight / Rhizoctonia loci:** no open mapping paper exists.
