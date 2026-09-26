-- CQ11: Which varieties recommended for zone Z lack reaction data for the priority diseases of their crop?
-- Rejected claims and predictions do not count as data (the views exclude them).
-- params: zone_id
SELECT zv.variety_id,
       v.name AS variety_name,
       d.id AS disease_id,
       d.name AS disease_name
FROM (SELECT DISTINCT variety_id FROM v_variety_zone WHERE zone_id = %(zone_id)s) zv
JOIN entity v ON v.id = zv.variety_id
JOIN entity d ON d.type = 'Disease' AND d.crop = v.crop
WHERE NOT EXISTS (
    SELECT 1 FROM v_variety_reaction r WHERE r.variety_id = zv.variety_id AND r.disease_id = d.id
)
ORDER BY v.name, d.id;
