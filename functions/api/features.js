/**
 * GET /api/features?variety_id=<id>      a numeric feature vector for one variety (RESEARCH_ROADMAP.md phase 10, for the phenomic and yield models)
 *
 * One entry per disease of the variety's crop: the susceptibility score of the best-supported reaction (S 1.0, MS 0.7, MR 0.35, R 0.1; the same scale the risk engine design uses),
 * 'known' (0/1), the evidence tier weight (A 1.0, B 0.75, C 0.5, D 0.25) and 'conflict' (0/1); plus the number of genes carried and of genes known to act on that disease, and one-hot zones.
 * An unknown reaction is reported as null with known = 0 -- never guessed. Reads kg_variety_profile, kg_diseases and kg_disease_profile.
 */

const JSON_HEADERS = { "content-type": "application/json; charset=utf-8" };
const SUSCEPTIBILITY = { HS: 1.0, S: 1.0, MS: 0.7, MR: 0.35, R: 0.1 };
const TIER_WEIGHT = { A: 1.0, B: 0.75, C: 0.5, D: 0.25 };

function json(status, body) {
  return new Response(JSON.stringify(body), { status, headers: JSON_HEADERS });
}

async function get(env, view, params) {
  const response = await fetch(`${env.SUPABASE_URL}/rest/v1/${view}?${params}`, {
    headers: { apikey: env.SUPABASE_PUBLISHABLE_KEY, Authorization: `Bearer ${env.SUPABASE_PUBLISHABLE_KEY}` },
  });
  if (!response.ok) throw new Error(`Supabase ${response.status} (${view}): ${await response.text()}`);
  return response.json();
}

export async function onRequestGet({ request, env }) {
  const varietyId = String(new URL(request.url).searchParams.get("variety_id") || "").trim();
  if (!varietyId) return json(400, { error: "Missing required query parameter: variety_id." });
  if (!env?.SUPABASE_URL || !env?.SUPABASE_PUBLISHABLE_KEY) return json(503, { error: "Supabase credentials are not configured for this environment." });
  try {
    const rows = await get(env, "kg_variety_profile", new URLSearchParams({ select: "*", id: `eq.${varietyId}`, limit: "1" }));
    if (!rows.length) return json(404, { error: `No variety with id ${varietyId}.` });
    const v = rows[0];
    const diseases = await get(env, "kg_disease_profile", new URLSearchParams({ select: "id,name,genes", crop: `eq.${v.crop}`, order: "name.asc" }));
    const carried = new Set(v.genes.map((g) => g.gene_id));
    const features = {};
    for (const d of diseases) {
      const slug = d.id.split(":").pop();
      // the best-supported reaction: highest tier, then the most sources
      const reactions = v.reactions.filter((r) => r.disease_id === d.id && SUSCEPTIBILITY[r.reaction] !== undefined);
      reactions.sort((a, b) => (TIER_WEIGHT[b.tier] ?? 0) - (TIER_WEIGHT[a.tier] ?? 0) || (b.n_sources ?? 0) - (a.n_sources ?? 0));
      const best = reactions[0];
      features[`${slug}.susceptibility`] = best ? SUSCEPTIBILITY[best.reaction] : null;
      features[`${slug}.known`] = best ? 1 : 0;
      features[`${slug}.tier_weight`] = best ? TIER_WEIGHT[best.tier] ?? 0 : 0;
      features[`${slug}.conflict`] = reactions.some((r) => r.conflict) ? 1 : 0;
      features[`${slug}.n_resistance_genes_carried`] = d.genes.filter((g) => carried.has(g.gene_id)).length;
    }
    features["n_genes_carried"] = v.genes.length;
    features["release_year"] = v.release_year ? Number(v.release_year) : null;
    for (const z of v.zones) features[`zone.${z.zone_id.split(":").pop()}`] = 1;
    return json(200, { variety_id: v.id, variety_name: v.name, crop: v.crop, version: "1", scale: { susceptibility: SUSCEPTIBILITY, tier_weight: TIER_WEIGHT }, features });
  } catch (error) {
    console.error("Features error:", error);
    return json(500, { error: error.message || "Database query failed" });
  }
}
