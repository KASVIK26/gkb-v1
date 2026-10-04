/**
 * GET /api/profile?type=variety|disease|gene&id=<entity id>     one profile (everything the KG holds about the entity, with tiers)
 * GET /api/profile?type=variety|disease|gene&crop=wheat&list=1  the entities to choose from: [{id, name}]
 *
 * Reads the public views kg_variety_profile / kg_disease_profile / kg_gene_profile (supabase/migrations/20261004000000_profile_views.sql).
 */

const JSON_HEADERS = { "content-type": "application/json; charset=utf-8" };
const VIEWS = { variety: ["kg_variety_profile", "kg_varieties"], disease: ["kg_disease_profile", "kg_diseases"], gene: ["kg_gene_profile", "kg_gene_list"] };

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
  const url = new URL(request.url);
  const type = String(url.searchParams.get("type") || "").toLowerCase();
  const id = String(url.searchParams.get("id") || "").trim();
  const crop = String(url.searchParams.get("crop") || "").trim().toLowerCase();
  if (!VIEWS[type]) return json(400, { error: "type must be variety, disease or gene." });
  if (!env?.SUPABASE_URL || !env?.SUPABASE_PUBLISHABLE_KEY) return json(503, { error: "Supabase credentials are not configured for this environment." });
  try {
    if (url.searchParams.get("list")) {
      const params = new URLSearchParams({ select: "id,name", order: "name.asc" });
      if (crop) params.set("crop", `eq.${crop}`);
      return json(200, { type, items: await get(env, VIEWS[type][1], params) });
    }
    if (!id) return json(400, { error: "Missing required query parameter: id." });
    const rows = await get(env, VIEWS[type][0], new URLSearchParams({ select: "*", id: `eq.${id}`, limit: "1" }));
    if (!rows.length) return json(404, { error: `No ${type} with id ${id}.` });
    return json(200, { type, profile: rows[0] });
  } catch (error) {
    console.error("Profile error:", error);
    return json(500, { error: error.message || "Database query failed" });
  }
}
