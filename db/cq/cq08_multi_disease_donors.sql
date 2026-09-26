-- CQ8: Which varieties/germplasm are resistance donors for several diseases?
-- A disease counts only if the variety has an R/MR reaction and no MS/S/HS reaction at the same stage.
-- params: crop, min_diseases
SELECT r.variety_id,
       v.name AS variety_name,
       count(DISTINCT r.disease_id) AS n_diseases,
       array_agg(DISTINCT r.disease_id ORDER BY r.disease_id) AS diseases
FROM v_variety_reaction r
JOIN entity v ON v.id = r.variety_id
WHERE r.reaction IN ('R', 'MR')
  AND v.crop = %(crop)s
  AND NOT EXISTS (
      SELECT 1 FROM v_variety_reaction s
      WHERE s.variety_id = r.variety_id AND s.disease_id = r.disease_id AND s.stage = r.stage
        AND s.reaction IN ('MS', 'S', 'HS')
  )
GROUP BY r.variety_id, v.name
HAVING count(DISTINCT r.disease_id) >= %(min_diseases)s
ORDER BY n_diseases DESC, v.name;
