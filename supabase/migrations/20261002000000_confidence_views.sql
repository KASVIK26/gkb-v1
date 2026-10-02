-- Expose computed confidence (curator/graph/scoring.py) and provenance through the public bridge
-- views, so the dashboard can show WHY a claim is trusted instead of only that it exists.
--
-- Additive only: every existing view keeps its current columns in their current order and gains new
-- ones at the end (the only change CREATE OR REPLACE VIEW permits), so nothing already reading
-- these views breaks. Until the release that carries scores is promoted, the new score/tier columns
-- are simply NULL.
--
-- kg_claim_evidence deliberately omits evidence.quote: the verbatim excerpts stay in the database for
-- audit and for the curation tools, but are not published through the anonymous REST API. Source
-- title, year, venue, link, evidence type and locator (section/table) are enough to check a claim.

CREATE OR REPLACE VIEW public.kg_claim_evidence AS
SELECT
    ev.claim_id,
    ev.source_id,
    s.type AS source_type,
    s.title AS source_title,
    s.year AS source_year,
    s.venue AS source_venue,
    s.url AS source_url,
    ev.method,
    ev.weight,
    ev.locator,
    (ev.reviewer IS NOT NULL) AS human_reviewed
FROM kg_current.evidence ev
JOIN kg_current.source s ON s.id = ev.source_id;

CREATE OR REPLACE VIEW public.kg_graph_edges AS
SELECT
    c.id AS claim_id,
    c.type AS claim_type,
    c.subject_id,
    c.object_id,
    c.tier,
    c.status,
    s.crop AS subject_crop,
    o.crop AS object_crop,
    c.score,
    c.conflict,
    (SELECT count(DISTINCT ev.source_id) FROM kg_current.evidence ev WHERE ev.claim_id = c.id) AS n_sources
FROM kg_current.claim c
JOIN kg_current.entity s ON s.id = c.subject_id
JOIN kg_current.entity o ON o.id = c.object_id
WHERE c.status IN ('reviewed', 'unreviewed');

CREATE OR REPLACE VIEW public.kg_variety_reactions AS
SELECT
    r.variety_id, v.name AS variety_name, r.disease_id, d.name AS disease_name,
    r.reaction, r.stage,
    r.claim_id, r.score, r.tier, r.conflict,
    (SELECT count(DISTINCT ev.source_id) FROM kg_current.evidence ev WHERE ev.claim_id = r.claim_id) AS n_sources
FROM kg_current.v_variety_reaction r
JOIN kg_current.entity v ON v.id = r.variety_id
JOIN kg_current.entity d ON d.id = r.disease_id;

CREATE OR REPLACE VIEW public.kg_gene_resistance AS
SELECT
    g.id AS gene_id, g.name AS gene_name, g.props ->> 'chromosome' AS chromosome,
    g.props ->> 'gene_class' AS gene_class, (g.props ->> 'cloned')::boolean AS cloned,
    r.disease_id, d.name AS disease_name, d.crop,
    r.resistance_type, r.spectrum,
    r.claim_id, r.score, r.tier,
    (SELECT count(DISTINCT ev.source_id) FROM kg_current.evidence ev WHERE ev.claim_id = r.claim_id) AS n_sources
FROM kg_current.v_gene_resistance r
JOIN kg_current.entity g ON g.id = r.gene_id
JOIN kg_current.entity d ON d.id = r.disease_id;

CREATE OR REPLACE VIEW public.kg_disease_triggers AS
SELECT
    t.disease_id, d.name AS disease_name, d.crop,
    t.trigger_id, tr.name AS trigger_name,
    t.phase, t.bbch_from, t.bbch_to, t.conditions,
    t.claim_id, c.score, t.tier,
    (SELECT count(DISTINCT ev.source_id) FROM kg_current.evidence ev WHERE ev.claim_id = t.claim_id) AS n_sources
FROM kg_current.v_disease_trigger t
JOIN kg_current.claim c ON c.id = t.claim_id
JOIN kg_current.entity d ON d.id = t.disease_id
JOIN kg_current.entity tr ON tr.id = t.trigger_id;

CREATE OR REPLACE VIEW public.kg_disease_advisories AS
SELECT
    a.disease_id, d.name AS disease_name, a.advisory_id, adv.name AS advisory_name,
    adv.props ->> 'action_type' AS action_type,
    a.claim_id, c.score, a.tier,
    (SELECT count(DISTINCT ev.source_id) FROM kg_current.evidence ev WHERE ev.claim_id = a.claim_id) AS n_sources
FROM kg_current.v_disease_advisory a
JOIN kg_current.claim c ON c.id = a.claim_id
JOIN kg_current.entity d ON d.id = a.disease_id
JOIN kg_current.entity adv ON adv.id = a.advisory_id;

GRANT SELECT ON public.kg_claim_evidence TO anon, authenticated;
