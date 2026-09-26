-- Public-schema bridge views for the demo dashboard (public/ + functions/), read via Supabase's
-- default REST API (PostgREST exposes the `public` schema out of the box -- no dashboard config
-- needed). Each view selects from kg_current, which is a schema of views that
-- curator/graph/promote.py repoints atomically on every release -- so these bridge views keep
-- resolving correctly after every future promotion without needing to be redefined.
--
-- IMPORTANT SCOPE NOTE: this is a DEMO query layer for exercising the KG interactively, not the
-- real risk-engine API (RESEARCH_ROADMAP.md Phase 11, still not built). In particular, the
-- sensor-trigger matching this enables (see functions/api/triggers.js) is a single-snapshot
-- comparison against submitted sensor values, not the real windowed/aggregated model each
-- EnvTrigger's own conditions (aggregation + window_h) describes -- there is no time-series
-- ingestion here, just a point-in-time check against whatever numbers are typed into the form.

CREATE OR REPLACE VIEW public.kg_stats AS
SELECT
    (SELECT count(*) FROM kg_current.entity WHERE type = 'Crop') AS crops,
    (SELECT count(*) FROM kg_current.entity WHERE type = 'Variety') AS varieties,
    (SELECT count(*) FROM kg_current.entity WHERE type IN ('Gene', 'QTL')) AS genes,
    (SELECT count(*) FROM kg_current.entity WHERE type = 'Disease') AS diseases,
    (SELECT count(*) FROM kg_current.claim) AS edges;

CREATE OR REPLACE VIEW public.kg_varieties AS
SELECT
    e.id, e.name, e.crop,
    e.props ->> 'release_year' AS release_year,
    e.props ->> 'releasing_institute' AS releasing_institute,
    (SELECT array_agg(s.synonym) FROM kg_current.entity_synonym s WHERE s.entity_id = e.id) AS synonyms
FROM kg_current.entity e
WHERE e.type = 'Variety';

CREATE OR REPLACE VIEW public.kg_diseases AS
SELECT id, name, crop FROM kg_current.entity WHERE type = 'Disease';

CREATE OR REPLACE VIEW public.kg_variety_reactions AS
SELECT
    r.variety_id, v.name AS variety_name, r.disease_id, d.name AS disease_name,
    r.reaction, r.stage
FROM kg_current.v_variety_reaction r
JOIN kg_current.entity v ON v.id = r.variety_id
JOIN kg_current.entity d ON d.id = r.disease_id;

CREATE OR REPLACE VIEW public.kg_gene_resistance AS
SELECT
    g.id AS gene_id, g.name AS gene_name, g.props ->> 'chromosome' AS chromosome,
    g.props ->> 'gene_class' AS gene_class, (g.props ->> 'cloned')::boolean AS cloned,
    r.disease_id, d.name AS disease_name, d.crop,
    r.resistance_type, r.spectrum
FROM kg_current.v_gene_resistance r
JOIN kg_current.entity g ON g.id = r.gene_id
JOIN kg_current.entity d ON d.id = r.disease_id;

CREATE OR REPLACE VIEW public.kg_disease_triggers AS
SELECT
    t.disease_id, d.name AS disease_name, d.crop,
    t.trigger_id, tr.name AS trigger_name,
    t.phase, t.bbch_from, t.bbch_to, t.conditions
FROM kg_current.v_disease_trigger t
JOIN kg_current.entity d ON d.id = t.disease_id
JOIN kg_current.entity tr ON tr.id = t.trigger_id;

CREATE OR REPLACE VIEW public.kg_disease_advisories AS
SELECT
    a.disease_id, d.name AS disease_name, a.advisory_id, adv.name AS advisory_name,
    adv.props ->> 'action_type' AS action_type
FROM kg_current.v_disease_advisory a
JOIN kg_current.entity d ON d.id = a.disease_id
JOIN kg_current.entity adv ON adv.id = a.advisory_id;

-- PostgREST queries as `anon` for unauthenticated requests (the publishable/anon key). A plain
-- view checks the querying role's privileges on the view itself; access to the underlying
-- kg_current/kg_<release> objects is then checked against the VIEW OWNER's privileges (standard
-- Postgres view semantics), so granting SELECT on just these bridge views is sufficient.
GRANT SELECT ON
    public.kg_stats, public.kg_varieties, public.kg_diseases,
    public.kg_variety_reactions, public.kg_gene_resistance,
    public.kg_disease_triggers, public.kg_disease_advisories
    TO anon, authenticated;
