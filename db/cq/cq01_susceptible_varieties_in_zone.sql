-- CQ1: Which varieties recommended for zone Z are susceptible (MS/S/HS) to disease D, and on what evidence?
-- params: zone_id, disease_id
SELECT r.variety_id,
       v.name AS variety_name,
       r.reaction, r.stage, r.pathotype_id, r.location, r.season, r.tier, r.claim_id,
       array_agg(DISTINCT ev.source_id ORDER BY ev.source_id) AS sources
FROM (SELECT DISTINCT variety_id FROM v_variety_zone WHERE zone_id = %(zone_id)s) z
JOIN v_variety_reaction r ON r.variety_id = z.variety_id
JOIN entity v ON v.id = r.variety_id
JOIN evidence ev ON ev.claim_id = r.claim_id
WHERE r.disease_id = %(disease_id)s
  AND r.reaction IN ('MS', 'S', 'HS')
GROUP BY r.variety_id, v.name, r.reaction, r.stage, r.pathotype_id, r.location, r.season, r.tier, r.claim_id
ORDER BY v.name, r.season NULLS LAST;
