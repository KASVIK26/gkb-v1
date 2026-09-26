-- Public-schema bridge views for the graph visualizer (docs/plans: paper-extraction review
-- pipeline + graph visualizer, 2026-09-27), read via Supabase's default REST API exactly like
-- migrations/20260926120000_dashboard_views.sql's kg_* views. Node/edge shape is chosen to map
-- directly onto Cytoscape.js's input format ({data: {id, ...}} / {data: {source, target, ...}}) --
-- see TECH_STACK.md Sec 3, which already names Cytoscape.js as the intended library for this.
--
-- Selects from kg_current, which curator/graph/promote.py repoints atomically on every release,
-- so these views keep resolving correctly after every future promotion without redefinition.

CREATE OR REPLACE VIEW public.kg_graph_nodes AS
SELECT
    e.id,
    e.type,
    e.name,
    e.crop
FROM kg_current.entity e;

CREATE OR REPLACE VIEW public.kg_graph_edges AS
SELECT
    c.id AS claim_id,
    c.type AS claim_type,
    c.subject_id,
    c.object_id,
    c.tier,
    c.status,
    s.crop AS subject_crop,
    o.crop AS object_crop
FROM kg_current.claim c
JOIN kg_current.entity s ON s.id = c.subject_id
JOIN kg_current.entity o ON o.id = c.object_id
WHERE c.status IN ('reviewed', 'unreviewed');

GRANT SELECT ON public.kg_graph_nodes, public.kg_graph_edges TO anon, authenticated;
