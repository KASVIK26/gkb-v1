/**
 * GET /api/stats
 *
 * Returns a snapshot of node/relationship counts from Neo4j AuraDB.
 * Intended for the stats bar in the frontend (E3).
 *
 * Response shape:
 *   { crops, varieties, genes, diseases, edges, treatments }
 */

const JSON_HEADERS = {
  "content-type": "application/json; charset=utf-8",
  // Cache for 5 minutes — counts don't change that often and this saves quota
  "cache-control": "public, max-age=300",
};

function json(status, body) {
  return new Response(JSON.stringify(body, null, 2), {
    status,
    headers: JSON_HEADERS,
  });
}

function resolveNeo4jDatabase(uri, database) {
  const configuredDatabase = String(database || "").trim();
  if (configuredDatabase) return configuredDatabase;

  const parsed = new URL(String(uri || "").trim());
  const auraHostMatch = parsed.hostname.match(/^([^.]+)\.databases\.neo4j\.io$/i);
  if (auraHostMatch) return auraHostMatch[1];
  return "neo4j";
}

function buildNeo4jQueryUrl(uri, database) {
  const trimmedUri = String(uri || "").trim().replace(/\/$/, "");
  if (!trimmedUri) throw new Error("NEO4J_URI is empty.");
  if (trimmedUri.endsWith("/query/v2")) return trimmedUri;

  let baseUrl = trimmedUri;
  if (/^(neo4j|bolt)(\+s)?:\/\//i.test(trimmedUri)) {
    const parsed = new URL(trimmedUri);
    baseUrl = `https://${parsed.host}`;
  } else if (!/^https?:\/\//i.test(trimmedUri)) {
    throw new Error("NEO4J_URI must start with neo4j+s://, neo4j://, bolt+s://, bolt://, http://, or https://.");
  }
  return `${baseUrl}/db/${encodeURIComponent(resolveNeo4jDatabase(trimmedUri, database))}/query/v2`;
}

async function queryNeo4j(uri, user, password, database, statement, params = {}) {
  const auth = btoa(`${user}:${password}`);
  const queryUrl = buildNeo4jQueryUrl(uri, database);

  const response = await fetch(queryUrl, {
    method: "POST",
    headers: {
      Accept: "application/json",
      Authorization: `Basic ${auth}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      statement: statement.replace(/\s+/g, " ").trim(),
      parameters: params,
    }),
  });

  const text = await response.text();
  const body = text ? JSON.parse(text) : {};

  if (!response.ok) {
    const neo4jErr = (body.errors || []).map((e) => `${e.code}: ${e.message}`).join("; ");
    throw new Error(`Neo4j ${response.status}: ${neo4jErr || body.message || response.statusText}`);
  }

  return body;
}

export async function onRequestGet({ env }) {
  if (!env?.NEO4J_URI || !env?.NEO4J_USER || !env?.NEO4J_PASSWORD) {
    return json(503, { error: "Neo4j credentials are not configured." });
  }

  const statsQuery = `
    MATCH (cr:Crop)    WITH count(cr) AS crops
    MATCH (v:Variety)  WITH crops, count(v) AS varieties
    MATCH (g:Gene)     WITH crops, varieties, count(g) AS genes
    MATCH (d:Disease)  WITH crops, varieties, genes, count(d) AS diseases
    MATCH ()-[r:CONFERS_RESISTANCE_TO]->() WITH crops, varieties, genes, diseases, count(r) AS edges
    MATCH (t:Treatment)
    RETURN crops, varieties, genes, diseases, edges, count(t) AS treatments
  `;

  try {
    const result = await queryNeo4j(
      env.NEO4J_URI,
      env.NEO4J_USER,
      env.NEO4J_PASSWORD,
      env.NEO4J_DATABASE,
      statsQuery,
    );

    const row = (result.data?.values || [[]])[0] || [];
    // Column order matches the RETURN clause above
    const [crops = 0, varieties = 0, genes = 0, diseases = 0, edges = 0, treatments = 0] = row;

    return json(200, { crops, varieties, genes, diseases, edges, treatments });
  } catch (error) {
    console.error("Stats query error:", error);
    return json(500, { error: error.message || "Database query failed" });
  }
}
