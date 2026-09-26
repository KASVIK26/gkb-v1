-- CQ9: How genetically vulnerable is zone Z? Share of the varieties recommended there that carry each gene.
-- (Unweighted. Weight by seed-chain/area share once that data is loaded.)
-- params: zone_id
WITH zone_varieties AS (
    SELECT DISTINCT variety_id FROM v_variety_zone WHERE zone_id = %(zone_id)s
), total AS (
    SELECT count(*) AS n FROM zone_varieties
)
SELECT c.gene_id,
       g.name AS gene_name,
       count(DISTINCT c.variety_id) AS n_varieties,
       round(100.0 * count(DISTINCT c.variety_id) / nullif(total.n, 0), 1) AS pct_of_zone_varieties
FROM zone_varieties zv
JOIN v_variety_carries c ON c.variety_id = zv.variety_id
JOIN entity g ON g.id = c.gene_id
CROSS JOIN total
GROUP BY c.gene_id, g.name, total.n
ORDER BY n_varieties DESC, g.name;
