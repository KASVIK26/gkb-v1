/**
 * POST /api/query   { crop, variety }    (variety is a var:<crop>:<LOCAL> id, or "__all__")
 *
 * Returns real slices of the live Supabase KG:
 *   - varietyReactions: VARIETY_REACTION claims for the selected variety (disease + reaction)
 *   - varietyGenes:     VARIETY_CARRIES_GENE claims for the selected variety, each with the diseases the gene
 *                       is claimed to confer resistance to and the pathotypes known to defeat it (kg_variety_genes)
 *   - geneResistance:   GENE_CONFERS_RESISTANCE claims for the crop (gene + disease); the crop-wide list
 *                       shown when no variety is selected
 *   - qtls:             QTL_ASSOCIATION claims for the crop (genome regions / GWAS loci linked to a disease, with position,
 *                       statistics and the reference genes in the region); never variety-specific
 *
 * Only a minority of varieties have gene claims (wheat only so far); an empty varietyGenes means "none
 * recorded in the KG", not "carries no gene", and the page says so.
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

    const qtls = await supabaseGet(
      env,
      "kg_qtl_associations",
      new URLSearchParams({ crop: `eq.${crop}`, order: "disease_name.asc,qtl_name.asc" }),
    );

    let varietyReactions = [];
    let varietyGenes = [];
    if (variety !== "__all__") {
      varietyGenes = await supabaseGet(
        env,
        "kg_variety_genes",
        new URLSearchParams({ variety_id: `eq.${variety}`, order: "gene_name.asc" }),
      );
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
      varietyGenes,
      qtls,
      counts: {
        geneResistance: geneResistance.length,
        varietyReactions: varietyReactions.length,
        varietyGenes: varietyGenes.length,
        qtls: qtls.length,
      },
    });
  } catch (error) {
    console.error("Query error:", error);
    return json(500, { error: error.message || "Database query failed" });
  }
}
