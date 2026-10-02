-- Structured advisory detail (product, dose, timing, growth stage, where it was tested) and the
-- properties of the entities a visitor can click in the graph. Additive: new columns are appended to
-- views that already exist (the only change CREATE OR REPLACE VIEW allows), so nothing reading them breaks.
-- Kept in a *_views.sql file so curator/graph/promote.py re-applies it after every promotion.

CREATE OR REPLACE VIEW public.kg_disease_advisories AS
SELECT
    a.disease_id, d.name AS disease_name, a.advisory_id, adv.name AS advisory_name,
    adv.props ->> 'action_type' AS action_type,
    a.claim_id, c.score, a.tier,
    (SELECT count(DISTINCT ev.source_id) FROM kg_current.evidence ev WHERE ev.claim_id = a.claim_id) AS n_sources,
    adv.props ->> 'active_ingredient' AS active_ingredient,
    adv.props ->> 'dose' AS dose,
    adv.props ->> 'timing' AS timing,
    (adv.props ->> 'bbch_from')::int AS bbch_from,
    (adv.props ->> 'bbch_to')::int AS bbch_to,
    adv.props ->> 'region' AS region
FROM kg_current.v_disease_advisory a
JOIN kg_current.claim c ON c.id = a.claim_id
JOIN kg_current.entity d ON d.id = a.disease_id
JOIN kg_current.entity adv ON adv.id = a.advisory_id;

-- Only advisories and triggers publish their props: their fields are the content (the same trigger
-- conditions are already served by kg_disease_triggers). Other entity types keep NULL.
CREATE OR REPLACE VIEW public.kg_graph_nodes AS
SELECT
    e.id,
    e.type,
    e.name,
    e.crop,
    CASE WHEN e.type IN ('Advisory', 'EnvTrigger') THEN e.props END AS props
FROM kg_current.entity e;
