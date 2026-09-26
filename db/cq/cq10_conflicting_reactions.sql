-- CQ10: Where is evidence conflicting? Same variety, disease, stage and pathotype context,
-- reported resistant in one claim and susceptible in another. R vs S against *different*
-- pathotypes is expected for race-specific genes and is not a conflict.
-- params: crop (text or NULL for all crops)
SELECT a.variety_id,
       v.name AS variety_name,
       a.disease_id, a.stage, a.pathotype_id,
       a.claim_id AS resistant_claim_id, a.reaction AS resistant_reaction,
       a.location AS resistant_location, a.season AS resistant_season,
       b.claim_id AS susceptible_claim_id, b.reaction AS susceptible_reaction,
       b.location AS susceptible_location, b.season AS susceptible_season
FROM v_variety_reaction a
JOIN v_variety_reaction b
  ON b.variety_id = a.variety_id
 AND b.disease_id = a.disease_id
 AND b.stage = a.stage
 AND b.pathotype_id IS NOT DISTINCT FROM a.pathotype_id
JOIN entity v ON v.id = a.variety_id
WHERE a.reaction IN ('R', 'MR')
  AND b.reaction IN ('MS', 'S', 'HS')
  AND (%(crop)s::text IS NULL OR v.crop = %(crop)s::text)
ORDER BY v.name, a.disease_id, a.claim_id, b.claim_id;
