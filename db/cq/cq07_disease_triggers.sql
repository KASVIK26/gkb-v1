-- CQ7: What environmental envelope favours disease D at each growth stage, with citations?
-- params: disease_id
SELECT t.trigger_id,
       t.phase, t.bbch_from, t.bbch_to, t.conditions, t.tier,
       array_agg(DISTINCT ev.source_id ORDER BY ev.source_id) AS sources,
       coalesce(array_agg(DISTINCT ev.quote ORDER BY ev.quote) FILTER (WHERE ev.quote IS NOT NULL), '{}') AS quotes
FROM v_disease_trigger t
JOIN evidence ev ON ev.claim_id = t.claim_id
WHERE t.disease_id = %(disease_id)s
GROUP BY t.trigger_id, t.phase, t.bbch_from, t.bbch_to, t.conditions, t.tier
ORDER BY t.bbch_from, t.phase;
