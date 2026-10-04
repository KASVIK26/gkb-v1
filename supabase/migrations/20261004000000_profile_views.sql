-- Profile views for the researcher dashboard (RESEARCH_ROADMAP.md phase 10: variety profile, disease page, gene page): one row per variety / disease / gene with everything the KG
-- holds about it as JSON arrays (empty when the KG has nothing). Each reaction, gene link and so on carries its tier, source count and conflict flag, so the page can show how
-- strong each statement is. Additive: new views only; re-applied by `agrihub kg promote` (every *_views.sql file is).

CREATE OR REPLACE VIEW public.kg_gene_list AS
SELECT id, name, crop FROM kg_current.entity WHERE type = 'Gene';

CREATE OR REPLACE VIEW public.kg_variety_profile AS
SELECT
    v.id, v.name, v.crop,
    v.props ->> 'release_year' AS release_year, v.props ->> 'releasing_institute' AS releasing_institute,
    v.props ->> 'pedigree' AS pedigree, v.props ->> 'notification' AS notification,
    COALESCE((SELECT jsonb_agg(s.synonym ORDER BY s.synonym) FROM kg_current.entity_synonym s WHERE s.entity_id = v.id), '[]'::jsonb) AS synonyms,
    COALESCE((
        SELECT jsonb_agg(jsonb_build_object(
                   'claim_id', c.id, 'zone_id', z.id, 'zone_name', z.name, 'sowing', c.qualifiers ->> 'sowing',
                   'water_regime', c.qualifiers ->> 'water_regime', 'season', c.qualifiers ->> 'season', 'tier', c.tier) ORDER BY z.name)
        FROM kg_current.claim c JOIN kg_current.entity z ON z.id = c.object_id
        WHERE c.type = 'VARIETY_RECOMMENDED_FOR_ZONE' AND c.subject_id = v.id AND c.status IN ('reviewed', 'unreviewed')
    ), '[]'::jsonb) AS zones,
    COALESCE((
        SELECT jsonb_agg(jsonb_build_object(
                   'claim_id', r.claim_id, 'disease_id', r.disease_id, 'disease_name', d.name, 'reaction', r.reaction, 'stage', r.stage,
                   'season', r.season, 'location', r.location, 'tier', r.tier, 'score', r.score, 'conflict', r.conflict,
                   'n_sources', (SELECT count(DISTINCT ev.source_id) FROM kg_current.evidence ev WHERE ev.claim_id = r.claim_id)) ORDER BY d.name, r.season)
        FROM kg_current.v_variety_reaction r JOIN kg_current.entity d ON d.id = r.disease_id
        WHERE r.variety_id = v.id
    ), '[]'::jsonb) AS reactions,
    COALESCE((
        SELECT jsonb_agg(jsonb_build_object(
                   'claim_id', k.claim_id, 'gene_id', g.id, 'gene_name', g.name, 'method', k.method, 'tier', k.tier,
                   'diseases', COALESCE((SELECT jsonb_agg(d.name ORDER BY d.name) FROM kg_current.v_gene_resistance gr JOIN kg_current.entity d ON d.id = gr.disease_id
                                         WHERE gr.gene_id = g.id), '[]'::jsonb)) ORDER BY g.name)
        FROM kg_current.v_variety_carries k JOIN kg_current.entity g ON g.id = k.gene_id
        WHERE k.variety_id = v.id
    ), '[]'::jsonb) AS genes
FROM kg_current.entity v
WHERE v.type = 'Variety';

CREATE OR REPLACE VIEW public.kg_disease_profile AS
SELECT
    d.id, d.name, d.crop,
    COALESCE((SELECT jsonb_agg(jsonb_build_object('id', p.id, 'name', p.name) ORDER BY p.name)
              FROM kg_current.v_disease_pathogen dp JOIN kg_current.entity p ON p.id = dp.pathogen_id WHERE dp.disease_id = d.id), '[]'::jsonb) AS pathogens,
    COALESCE((SELECT jsonb_agg(jsonb_build_object('claim_id', gr.claim_id, 'gene_id', g.id, 'gene_name', g.name, 'resistance_type', gr.resistance_type,
                                                  'spectrum', gr.spectrum, 'chromosome', g.props ->> 'chromosome', 'tier', gr.tier) ORDER BY g.name)
              FROM kg_current.v_gene_resistance gr JOIN kg_current.entity g ON g.id = gr.gene_id WHERE gr.disease_id = d.id), '[]'::jsonb) AS genes,
    COALESCE((SELECT jsonb_agg(jsonb_build_object('claim_id', qa.claim_id, 'qtl_name', q.name, 'chromosome', q.props ->> 'chromosome', 'stage', qa.stage,
                                                  'pve_pct', qa.pve_pct, 'lod', qa.lod, 'tier', qa.tier) ORDER BY q.name)
              FROM kg_current.v_qtl_association qa JOIN kg_current.entity q ON q.id = qa.qtl_id WHERE qa.disease_id = d.id), '[]'::jsonb) AS qtls,
    COALESCE((SELECT jsonb_agg(jsonb_build_object('claim_id', t.claim_id, 'phase', t.phase, 'bbch_from', t.bbch_from, 'bbch_to', t.bbch_to,
                                                  'conditions', t.conditions, 'tier', t.tier) ORDER BY t.phase)
              FROM kg_current.v_disease_trigger t WHERE t.disease_id = d.id), '[]'::jsonb) AS triggers,
    COALESCE((SELECT jsonb_agg(jsonb_build_object('claim_id', a.claim_id, 'name', adv.name, 'action_type', adv.props ->> 'action_type',
                                                  'product', adv.props ->> 'active_ingredient', 'dose', adv.props ->> 'dose', 'timing', adv.props ->> 'timing',
                                                  'region', adv.props ->> 'region', 'tier', a.tier) ORDER BY adv.name)
              FROM kg_current.v_disease_advisory a JOIN kg_current.entity adv ON adv.id = a.advisory_id WHERE a.disease_id = d.id), '[]'::jsonb) AS advisories,
    COALESCE((SELECT jsonb_agg(jsonb_build_object('claim_id', pp.claim_id, 'pathotype', pt.name, 'zone', z.name, 'years', pp.years, 'frequency_pct', pp.frequency_pct, 'tier', pp.tier)
                               ORDER BY pp.years DESC, pp.frequency_pct DESC)
              FROM kg_current.v_pathotype_prevalence pp
              JOIN kg_current.entity pt ON pt.id = pp.pathotype_id
              JOIN kg_current.entity z ON z.id = pp.zone_id
              WHERE EXISTS (SELECT 1 FROM kg_current.v_disease_pathogen dp
                            WHERE dp.disease_id = d.id AND pp.pathotype_id LIKE 'pt:' || substr(dp.pathogen_id, 6) || ':%')), '[]'::jsonb) AS pathotype_prevalence,
    (SELECT count(DISTINCT r.variety_id) FROM kg_current.v_variety_reaction r WHERE r.disease_id = d.id AND r.reaction IN ('R', 'MR')) AS n_resistant_varieties,
    (SELECT count(DISTINCT r.variety_id) FROM kg_current.v_variety_reaction r WHERE r.disease_id = d.id AND r.reaction IN ('MS', 'S', 'HS')) AS n_susceptible_varieties,
    COALESCE((SELECT jsonb_agg(x ORDER BY x ->> 'variety_name') FROM (
                SELECT DISTINCT ON (r.variety_id) jsonb_build_object('variety_id', r.variety_id, 'variety_name', v.name, 'reaction', r.reaction, 'tier', r.tier, 'conflict', r.conflict) AS x
                FROM kg_current.v_variety_reaction r JOIN kg_current.entity v ON v.id = r.variety_id
                WHERE r.disease_id = d.id AND r.reaction IN ('R', 'MR')
                ORDER BY r.variety_id, r.score DESC NULLS LAST) s), '[]'::jsonb) AS resistant_varieties
FROM kg_current.entity d
WHERE d.type = 'Disease';

CREATE OR REPLACE VIEW public.kg_gene_profile AS
SELECT
    g.id, g.name, g.crop,
    g.props ->> 'chromosome' AS chromosome, g.props ->> 'gene_class' AS gene_class, g.props ->> 'origin_species' AS origin_species, (g.props ->> 'cloned')::boolean AS cloned,
    COALESCE((SELECT jsonb_agg(jsonb_build_object('claim_id', gr.claim_id, 'disease_id', d.id, 'disease_name', d.name, 'resistance_type', gr.resistance_type,
                                                  'spectrum', gr.spectrum, 'tier', gr.tier) ORDER BY d.name)
              FROM kg_current.v_gene_resistance gr JOIN kg_current.entity d ON d.id = gr.disease_id WHERE gr.gene_id = g.id), '[]'::jsonb) AS diseases,
    COALESCE((SELECT jsonb_agg(jsonb_build_object('claim_id', k.claim_id, 'variety_id', v.id, 'variety_name', v.name, 'method', k.method, 'tier', k.tier) ORDER BY v.name)
              FROM kg_current.v_variety_carries k JOIN kg_current.entity v ON v.id = k.variety_id WHERE k.gene_id = g.id), '[]'::jsonb) AS carriers,
    COALESCE((SELECT jsonb_agg(jsonb_build_object('claim_id', gp.claim_id, 'pathotype', p.name, 'outcome', gp.outcome, 'year', gp.year, 'region', gp.region) ORDER BY p.name)
              FROM kg_current.v_gene_pathotype gp JOIN kg_current.entity p ON p.id = gp.pathotype_id WHERE gp.gene_id = g.id), '[]'::jsonb) AS pathotypes
FROM kg_current.entity g
WHERE g.type = 'Gene';

GRANT SELECT ON public.kg_gene_list, public.kg_variety_profile, public.kg_disease_profile, public.kg_gene_profile TO anon, authenticated;
