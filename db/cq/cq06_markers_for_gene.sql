-- CQ6: Which markers can confirm gene G in a breeding line (diagnostic first, then closest linked)?
-- params: gene_id
SELECT m.marker_id,
       mk.name AS marker_name,
       mk.props ->> 'marker_type' AS marker_type,
       m.diagnostic, m.distance_cm, m.tier,
       array_agg(DISTINCT ev.source_id ORDER BY ev.source_id) AS sources
FROM v_marker_linkage m
JOIN entity mk ON mk.id = m.marker_id
JOIN evidence ev ON ev.claim_id = m.claim_id
WHERE m.target_id = %(gene_id)s
GROUP BY m.marker_id, mk.name, mk.props, m.diagnostic, m.distance_cm, m.tier
ORDER BY m.diagnostic DESC, m.distance_cm NULLS LAST, mk.name;
