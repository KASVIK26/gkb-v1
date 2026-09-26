-- CQ4: Which genes have been defeated by which pathotypes, and when/where was this first reported?
-- params: crop (text or NULL for all crops)
SELECT d.gene_id,
       g.name AS gene_name,
       d.pathotype_id,
       pt.name AS pathotype_name,
       min(d.year) AS first_reported_year,
       coalesce(array_agg(DISTINCT d.region ORDER BY d.region) FILTER (WHERE d.region IS NOT NULL), '{}') AS regions,
       array_agg(DISTINCT d.claim_id ORDER BY d.claim_id) AS claim_ids
FROM v_gene_pathotype d
JOIN entity g ON g.id = d.gene_id
JOIN entity pt ON pt.id = d.pathotype_id
WHERE d.outcome = 'defeated'
  AND (%(crop)s::text IS NULL OR g.crop = %(crop)s::text)
GROUP BY d.gene_id, g.name, d.pathotype_id, pt.name
ORDER BY first_reported_year NULLS LAST, g.name;
