/**
 * GET /api/graph
 *
 * Returns the full node/edge graph from the live Supabase KG (kg_current release), via the
 * public.kg_graph_nodes / public.kg_graph_edges bridge views
 * (supabase/migrations/20260927010000_graph_views.sql).
 *
 * At 210 entities / 315 claims the whole graph fits comfortably in one response, so the frontend
 * fetches this once, caches it in memory, and does all crop/disease/relationship-type filtering
 * client-side (see public/app.js renderGraph()) instead of round-tripping on every filter change.
 *
 * Response shape: { nodes: [{id, type, name, crop}], edges: [{claim_id, claim_type, subject_id,
 * object_id, tier, status, subject_crop, object_crop}], counts: {nodes, edges} }
 */

const JSON_HEADERS = {
  "content-type": "application/json; charset=utf-8",
  // Cache for 5 minutes -- matches /api/stats; the graph only changes on a kg promote.
  "cache-control": "public, max-age=300",
};

function json(status, body) {
  return new Response(JSON.stringify(body, null, 2), { status, headers: JSON_HEADERS });
}

async function supabaseGet(env, view, params) {
  const response = await fetch(`${env.SUPABASE_URL}/rest/v1/${view}?${params}`, {
    headers: {
      apikey: env.SUPABASE_PUBLISHABLE_KEY,
      Authorization: `Bearer ${env.SUPABASE_PUBLISHABLE_KEY}`,
    },
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Supabase ${response.status} (${view}): ${text}`);
  }
  return response.json();
}

export async function onRequestGet({ env }) {
  if (!env?.SUPABASE_URL || !env?.SUPABASE_PUBLISHABLE_KEY) {
    return json(503, { error: "Supabase credentials are not configured for this environment." });
  }

  try {
    const [nodes, edges] = await Promise.all([
      supabaseGet(env, "kg_graph_nodes", new URLSearchParams({ order: "type.asc,name.asc" })),
      supabaseGet(env, "kg_graph_edges", new URLSearchParams({ order: "claim_type.asc" })),
    ]);

    return json(200, { nodes, edges, counts: { nodes: nodes.length, edges: edges.length } });
  } catch (error) {
    console.error("Graph query error:", error);
    return json(500, { error: error.message || "Database query failed" });
  }
}
