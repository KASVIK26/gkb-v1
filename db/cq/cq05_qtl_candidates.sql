-- CQ5: Which QTLs are associated with disease D, where do they map, and which NLR genes lie in their interval?
-- params: disease_id
SELECT q.qtl_id,
       e.name AS qtl_name,
       e.props ->> 'chromosome' AS chromosome,
       q.assembly, q.start_bp, q.end_bp, q.lod, q.pve_pct, q.population, q.tier,
       count(DISTINCT qc.ref_gene_id) AS genes_in_interval,
       coalesce(array_agg(DISTINCT rg.id ORDER BY rg.id)
                FILTER (WHERE (rg.props ->> 'is_nlr')::boolean), '{}') AS nlr_candidates
FROM v_qtl_association q
JOIN entity e ON e.id = q.qtl_id
LEFT JOIN v_qtl_contains qc ON qc.qtl_id = q.qtl_id
LEFT JOIN entity rg ON rg.id = qc.ref_gene_id
WHERE q.disease_id = %(disease_id)s
GROUP BY q.qtl_id, e.name, e.props, q.assembly, q.start_bp, q.end_bp, q.lod, q.pve_pct, q.population, q.tier
ORDER BY q.lod DESC NULLS LAST, e.name;
