/**
 * POST /api/query   { crop, variety }    (variety is a var:<crop>:<LOCAL> id, or "__all__")
 *
 * Returns two independent, real slices of the live Supabase KG:
 *   - varietyReactions: VARIETY_REACTION claims for the selected variety (disease + reaction)
 *   - geneResistance:   GENE_CONFERS_RESISTANCE claims for the crop (gene + disease)
 *
 * These are kept separate rather than joined into one "edge" list like the old Neo4j-era
 * response: the KG currently has no VARIETY_CARRIES_GENE claims loaded (see PHASES.md), so a
 * variety selection cannot honestly be used to filter which genes apply -- showing them as two
 * lists is what the real data supports, not a simplification for its own sake.
 */

const JSON_HEADERS = { "content-type": "application/json; charset=utf-8" };

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

export async function onRequestPost({ request, env }) {
  let payload;
  try {
    payload = await request.json();
  } catch {
    return json(400, { error: "Request body must be valid JSON." });
  }

  const crop = String(payload.crop || "").trim().toLowerCase();
  const variety = String(payload.variety || "__all__").trim();

  if (!crop) {
    return json(400, { error: "Missing required field: crop." });
  }

  if (!env?.SUPABASE_URL || !env?.SUPABASE_PUBLISHABLE_KEY) {
    return json(503, { error: "Supabase credentials are not configured for this environment." });
  }

  try {
    const geneResistance = await supabaseGet(
      env,
      "kg_gene_resistance",
      new URLSearchParams({ crop: `eq.${crop}`, order: "gene_name.asc" }),
    );

    let varietyReactions = [];
    if (variety !== "__all__") {
      varietyReactions = await supabaseGet(
        env,
        "kg_variety_reactions",
        new URLSearchParams({ variety_id: `eq.${variety}`, order: "disease_name.asc" }),
      );
    }

    return json(200, {
      query: { crop, variety },
      geneResistance,
      varietyReactions,
      counts: { geneResistance: geneResistance.length, varietyReactions: varietyReactions.length },
    });
  } catch (error) {
    console.error("Query error:", error);
    return json(500, { error: error.message || "Database query failed" });
  }
}
