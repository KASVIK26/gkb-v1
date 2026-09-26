/**
 * GET /api/stats
 *
 * Returns a snapshot of entity/claim counts from the live Supabase KG (kg_current release),
 * via the public.kg_stats bridge view (supabase/migrations/20260926120000_dashboard_views.sql).
 * Intended for the stats bar in the frontend.
 *
 * Response shape:
 *   { crops, varieties, genes, diseases, edges }
 */

const JSON_HEADERS = {
  "content-type": "application/json; charset=utf-8",
  // Cache for 5 minutes -- counts don't change that often and this saves quota.
  "cache-control": "public, max-age=300",
};

function json(status, body) {
  return new Response(JSON.stringify(body, null, 2), { status, headers: JSON_HEADERS });
}

export async function onRequestGet({ env }) {
  if (!env?.SUPABASE_URL || !env?.SUPABASE_PUBLISHABLE_KEY) {
    return json(503, { error: "Supabase credentials are not configured for this environment." });
  }

  try {
    const response = await fetch(`${env.SUPABASE_URL}/rest/v1/kg_stats`, {
      headers: {
        apikey: env.SUPABASE_PUBLISHABLE_KEY,
        Authorization: `Bearer ${env.SUPABASE_PUBLISHABLE_KEY}`,
      },
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Supabase ${response.status}: ${text}`);
    }

    const rows = await response.json();
    const row = rows[0] || {};

    return json(200, {
      crops: row.crops ?? 0,
      varieties: row.varieties ?? 0,
      genes: row.genes ?? 0,
      diseases: row.diseases ?? 0,
      edges: row.edges ?? 0,
    });
  } catch (error) {
    console.error("Stats query error:", error);
    return json(500, { error: error.message || "Database query failed" });
  }
}
