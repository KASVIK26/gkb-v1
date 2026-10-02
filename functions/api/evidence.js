/**
 * GET /api/evidence?claim_id=claim:<hex>
 *
 * The sources behind one claim: title, year, venue, link, kind of evidence and where in the source it
 * comes from, via public.kg_claim_evidence (supabase/migrations/20261002000000_confidence_views.sql).
 * Verbatim quotes are intentionally not part of that view -- they stay in the database for audit.
 */

const JSON_HEADERS = {
  "content-type": "application/json; charset=utf-8",
  // Evidence only changes on a kg promote, like the rest of the read API.
  "cache-control": "public, max-age=300",
};

function json(status, body) {
  return new Response(JSON.stringify(body, null, 2), { status, headers: JSON_HEADERS });
}

export async function onRequestGet({ request, env }) {
  const claimId = new URL(request.url).searchParams.get("claim_id") || "";
  if (!/^claim:[0-9a-f]{8,64}$/.test(claimId)) {
    return json(400, { error: "claim_id must look like claim:<hex>." });
  }
  if (!env?.SUPABASE_URL || !env?.SUPABASE_PUBLISHABLE_KEY) {
    return json(503, { error: "Supabase credentials are not configured for this environment." });
  }

  try {
    const params = new URLSearchParams({ claim_id: `eq.${claimId}`, order: "source_year.desc.nullslast" });
    const response = await fetch(`${env.SUPABASE_URL}/rest/v1/kg_claim_evidence?${params}`, {
      headers: {
        apikey: env.SUPABASE_PUBLISHABLE_KEY,
        Authorization: `Bearer ${env.SUPABASE_PUBLISHABLE_KEY}`,
      },
    });
    if (!response.ok) throw new Error(`Supabase ${response.status} (kg_claim_evidence): ${await response.text()}`);
    return json(200, { claim_id: claimId, evidence: await response.json() });
  } catch (error) {
    console.error("Evidence query error:", error);
    return json(500, { error: error.message || "Database query failed" });
  }
}
