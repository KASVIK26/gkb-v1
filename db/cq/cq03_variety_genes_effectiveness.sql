-- CQ3: Which resistance genes does variety V carry, how was that determined, and which of them have been
--      defeated by pathotypes prevalent in V's zones since a given year?
-- params: variety_id, since_year
WITH defeated_here AS (
    SELECT DISTINCT d.gene_id, d.pathotype_id
    FROM v_gene_pathotype d
    JOIN v_pathotype_prevalence p ON p.pathotype_id = d.pathotype_id
    JOIN v_variety_zone vz ON vz.zone_id = p.zone_id AND vz.variety_id = %(variety_id)s
    WHERE d.outcome = 'defeated'
      AND EXISTS (SELECT 1 FROM unnest(p.years) AS y WHERE y >= %(since_year)s)
)
SELECT c.gene_id,
       g.name AS gene_name,
       c.method, c.tier,
       coalesce(array_agg(DISTINCT dh.pathotype_id ORDER BY dh.pathotype_id)
                FILTER (WHERE dh.pathotype_id IS NOT NULL), '{}') AS defeated_by_prevalent_pathotypes
FROM v_variety_carries c
JOIN entity g ON g.id = c.gene_id
LEFT JOIN defeated_here dh ON dh.gene_id = c.gene_id
WHERE c.variety_id = %(variety_id)s
GROUP BY c.gene_id, g.name, c.method, c.tier
ORDER BY g.name, c.method;
