-- Variety-specific gene resistance for the dashboard: the genes a variety carries (VARIETY_CARRIES_GENE), how that was established (method),
-- and for each gene the diseases it is claimed to confer resistance to and the pathotypes known to defeat it or to be stopped by it
-- (CQ3, db/cq/cq03_variety_genes_effectiveness.sql). One row per variety-gene claim; `confers` and `pathotypes` are JSON arrays that
-- are empty when the KG has no such claim for the gene (the dashboard says so instead of guessing).
--
-- Additive: a new view; nothing existing changes. Re-applied by `agrihub kg promote` (every *_views.sql file is).

CREATE OR REPLACE VIEW public.kg_variety_genes AS
SELECT
    v.id AS variety_id, v.name AS variety_name, v.crop,
    k.gene_id, g.name AS gene_name, g.props ->> 'gene_class' AS gene_class,
    k.method, k.allele,
    k.claim_id, k.score, k.tier,
    (SELECT count(DISTINCT ev.source_id) FROM kg_current.evidence ev WHERE ev.claim_id = k.claim_id) AS n_sources,
    COALESCE((
        SELECT jsonb_agg(jsonb_build_object(
                   'claim_id', r.claim_id, 'disease_id', r.disease_id, 'disease_name', d.name,
                   'resistance_type', r.resistance_type, 'spectrum', r.spectrum, 'tier', r.tier) ORDER BY d.name)
        FROM kg_current.v_gene_resistance r
        JOIN kg_current.entity d ON d.id = r.disease_id
        WHERE r.gene_id = k.gene_id
    ), '[]'::jsonb) AS confers,
    COALESCE((
        SELECT jsonb_agg(jsonb_build_object(
                   'claim_id', gp.claim_id, 'pathotype', p.name, 'outcome', gp.outcome, 'year', gp.year, 'region', gp.region) ORDER BY p.name)
        FROM kg_current.v_gene_pathotype gp
        JOIN kg_current.entity p ON p.id = gp.pathotype_id
        WHERE gp.gene_id = k.gene_id
    ), '[]'::jsonb) AS pathotypes
FROM kg_current.v_variety_carries k
JOIN kg_current.entity v ON v.id = k.variety_id
JOIN kg_current.entity g ON g.id = k.gene_id;

GRANT SELECT ON public.kg_variety_genes TO anon, authenticated;
