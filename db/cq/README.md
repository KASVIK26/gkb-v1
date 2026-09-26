# Competency questions (CQs) as SQL

Each file answers one CQ from RESEARCH_ROADMAP.md §1.2 against a KG release schema.
Run a file with `curator.graph.pg.run_cq(conn, schema, "<file stem>", **params)`.
Parameters use psycopg named style (`%(name)s`).

| CQ | File | Status |
|---|---|---|
| CQ1 susceptible varieties in a zone | `cq01_susceptible_varieties_in_zone.sql` | tested |
| CQ2 IoT flag: favourable conditions AND variety not resistant | — | Phase 8: needs sensor data (`ops` schema) and the risk engine |
| CQ3 genes a variety carries and whether prevalent pathotypes defeat them | `cq03_variety_genes_effectiveness.sql` | tested |
| CQ4 defeated genes and first report | `cq04_defeated_genes.sql` | tested |
| CQ5 QTLs and NLR candidates in their interval | `cq05_qtl_candidates.sql` | tested |
| CQ6 markers to confirm a gene | `cq06_markers_for_gene.sql` | tested |
| CQ7 environmental triggers with citations | `cq07_disease_triggers.sql` | tested |
| CQ8 multi-disease donors | `cq08_multi_disease_donors.sql` | tested |
| CQ9 zone reliance on single genes | `cq09_zone_gene_reliance.sql` | tested (unweighted) |
| CQ10 conflicting evidence | `cq10_conflicting_reactions.sql` | tested |
| CQ11 reaction-data gaps | `cq11_reaction_gaps.sql` | tested |
| CQ12 prior plausibility for a phenomic prediction | — | Phase 11: needs the risk engine and priors |

Tests: `tests/test_cq.py` loads a synthetic toy KG (`tests/kg_toy.py`) into a throwaway Postgres and checks the
expected answer for every CQ. The toy data uses obviously fake names (TESTV1, TestYr1, ...) so it can never be
mistaken for real knowledge.
