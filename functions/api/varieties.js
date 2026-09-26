/**
 * GET /api/varieties?crop=wheat
 *
 * Lists variety names for a crop from the live Supabase KG, via public.kg_varieties.
 */

const JSON_HEADERS = { "content-type": "application/json; charset=utf-8" };

function json(status, body) {
  return new Response(JSON.stringify(body, null, 2), { status, headers: JSON_HEADERS });
}

export async function onRequestGet({ request, env }) {
  const url = new URL(request.url);
  const crop = String(url.searchParams.get("crop") || "").trim().toLowerCase();

  if (!crop) {
    return json(400, { error: "Missing required query parameter: crop." });
  }

  if (!env?.SUPABASE_URL || !env?.SUPABASE_PUBLISHABLE_KEY) {
    return json(503, { error: "Supabase credentials are not configured for this environment." });
  }

  try {
    const params = new URLSearchParams({
      crop: `eq.${crop}`,
      select: "id,name",
      order: "name.asc",
    });

    const response = await fetch(`${env.SUPABASE_URL}/rest/v1/kg_varieties?${params}`, {
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
    // The frontend's variety <select> keys off the display name (matches the old behaviour);
    // id is included so callers that want the stable identifier can use it directly.
    const varieties = rows.map((r) => ({ id: r.id, name: r.name }));

    return json(200, { crop, varieties, count: varieties.length });
  } catch (error) {
    console.error("Varieties query error:", error);
    return json(500, { error: error.message || "Database query failed" });
  }
}
