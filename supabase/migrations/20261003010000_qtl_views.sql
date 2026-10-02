-- Genome regions (QTL / GWAS loci) linked to a disease, for the dashboard's Browse tab: one row per QTL_ASSOCIATION claim, with the position and statistics the claim carries
-- and the reference genes found in the region (QTL_CONTAINS_REFGENE) as a JSON array (empty when the KG holds none).
--
-- Additive: a new view; nothing existing changes. Re-applied by `agrihub kg promote` (every *_views.sql file is).

CREATE OR REPLACE VIEW public.kg_qtl_associations AS
SELECT
    c.id AS claim_id,
    q.id AS qtl_id, q.name AS qtl_name, q.props ->> 'chromosome' AS chromosome, q.props ->> 'trait' AS trait,
    d.id AS disease_id, d.name AS disease_name, d.crop,
    c.qualifiers ->> 'stage' AS stage,
    c.qualifiers ->> 'assembly' AS assembly,
    (c.qualifiers ->> 'start_bp')::bigint AS start_bp, (c.qualifiers ->> 'end_bp')::bigint AS end_bp,
    c.qualifiers ->> 'left_marker' AS left_marker, c.qualifiers ->> 'right_marker' AS right_marker,
    (c.qualifiers ->> 'lod')::double precision AS lod, (c.qualifiers ->> 'pve_pct')::double precision AS pve_pct,
    (c.qualifiers ->> 'p_value')::double precision AS p_value, (c.qualifiers ->> 'n_env')::int AS n_env,
    c.qualifiers ->> 'population' AS population,
    c.score, c.tier, c.conflict,
    (SELECT count(DISTINCT ev.source_id) FROM kg_current.evidence ev WHERE ev.claim_id = c.id) AS n_sources,
    COALESCE((
        SELECT jsonb_agg(jsonb_build_object(
                   'gene', g.name, 'start_bp', (g.props ->> 'start_bp')::bigint, 'end_bp', (g.props ->> 'end_bp')::bigint,
                   'assembly', g.props ->> 'assembly', 'description', g.props ->> 'description') ORDER BY (g.props ->> 'start_bp')::bigint)
        FROM kg_current.claim k
        JOIN kg_current.entity g ON g.id = k.object_id
        WHERE k.type = 'QTL_CONTAINS_REFGENE' AND k.subject_id = c.subject_id AND k.status IN ('reviewed', 'unreviewed')
    ), '[]'::jsonb) AS genes
FROM kg_current.claim c
JOIN kg_current.entity q ON q.id = c.subject_id
JOIN kg_current.entity d ON d.id = c.object_id
WHERE c.type = 'QTL_ASSOCIATION' AND c.status IN ('reviewed', 'unreviewed');

GRANT SELECT ON public.kg_qtl_associations TO anon, authenticated;
