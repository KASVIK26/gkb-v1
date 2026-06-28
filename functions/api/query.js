const JSON_HEADERS = {
  "content-type": "application/json; charset=utf-8",
};

function json(status, body) {
  return new Response(JSON.stringify(body, null, 2), {
    status,
    headers: JSON_HEADERS,
  });
}

function resolveNeo4jDatabase(uri, database) {
  const configuredDatabase = String(database || "").trim();

  if (configuredDatabase) {
    return configuredDatabase;
  }

  const parsed = new URL(String(uri || "").trim());
  const auraHostMatch = parsed.hostname.match(/^([^.]+)\.databases\.neo4j\.io$/i);

  if (auraHostMatch) {
    return auraHostMatch[1];
  }

  return "neo4j";
}

function buildNeo4jQueryUrl(uri, database) {
  const trimmedUri = String(uri || "").trim().replace(/\/$/, "");

  if (!trimmedUri) {
    throw new Error("NEO4J_URI is empty.");
  }

  if (trimmedUri.endsWith("/query/v2")) {
    return trimmedUri;
  }

  let baseUrl = trimmedUri;

  if (/^(neo4j|bolt)(\+s)?:\/\//i.test(trimmedUri)) {
    const parsed = new URL(trimmedUri);
    baseUrl = `https://${parsed.host}`;
  } else if (!/^https?:\/\//i.test(trimmedUri)) {
    throw new Error(
      "NEO4J_URI must start with neo4j+s://, neo4j://, bolt+s://, bolt://, http://, or https://.",
    );
  }

  return `${baseUrl}/db/${encodeURIComponent(resolveNeo4jDatabase(trimmedUri, database))}/query/v2`;
}

function formatNeo4jErrors(body) {
  if (!Array.isArray(body?.errors) || body.errors.length === 0) {
    return "";
  }

  return body.errors
    .map((error) => `${error.code || "Neo4jError"}: ${error.message || "Unknown error"}`)
    .join("; ");
}

async function readResponseBody(response) {
  const text = await response.text();

  if (!text) {
    return {};
  }

  try {
    return JSON.parse(text);
  } catch {
    return { message: text };
  }
}

function formatList(value) {
  if (!Array.isArray(value)) {
    return value ?? null;
  }

  const values = [...new Set(value.filter((item) => item !== null && item !== ""))];
  return values.length ? values.join("; ") : null;
}

function normalizeEdge(edge) {
  return {
    ...edge,
    treatment: formatList(edge.treatment),
    iotTrigger: formatList(edge.iotTrigger),
  };
}

/**
 * Execute a parameterized Cypher query against Neo4j's HTTPS Query API.
 * This keeps Cloudflare Pages Functions on fetch(), avoiding Bolt driver sockets.
 */
async function queryNeo4j(uri, user, password, database, query, params = {}) {
  const auth = btoa(`${user}:${password}`);
  const queryUrl = buildNeo4jQueryUrl(uri, database);

  try {
    const response = await fetch(queryUrl, {
      method: "POST",
      headers: {
        Accept: "application/json",
        Authorization: `Basic ${auth}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        statement: query.replace(/\s+/g, " ").trim(),
        parameters: params,
      }),
    });

    const body = await readResponseBody(response);
    const neo4jErrors = formatNeo4jErrors(body);

    if (!response.ok) {
      throw new Error(
        `Neo4j Query API failed: ${response.status} ${response.statusText}${
          neo4jErrors ? ` - ${neo4jErrors}` : body.message ? ` - ${body.message}` : ""
        }`,
      );
    }

    if (neo4jErrors) {
      throw new Error(`Neo4j query failed: ${neo4jErrors}`);
    }

    return body;
  } catch (error) {
    throw new Error(`Neo4j connection error: ${error.message}`);
  }
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

  if (!env?.NEO4J_URI || !env?.NEO4J_USER || !env?.NEO4J_PASSWORD) {
    return json(503, {
      error: "Neo4j credentials are not configured for this environment.",
    });
  }

  try {
    // Build parameterized query
    let query;
    let params;

    if (variety === "__all__") {
      // Get all edges for a crop
      query = `
        MATCH (crop:Crop {name: $crop})
        MATCH (crop)<-[:BELONGS_TO]-(v:Variety)
        MATCH (v)-[carries:CARRIES]->(g:Gene)
        MATCH (g)-[resistance:CONFERS_RESISTANCE_TO]->(d:Disease)
        MATCH (d)-[:TREATED_BY]->(t:Treatment)
        WITH
          g,
          d,
          resistance,
          collect(DISTINCT v.name) as varieties,
          collect(DISTINCT t.action) as treatments,
          collect(DISTINCT t.iot_trigger) as iotTriggers
        RETURN {
          gene: g.id,
          chromosome: g.chromosome,
          allele: g.allele,
          resistanceType: g.resistance_type,
          disease: d.name,
          pathogen: d.pathogen,
          confidence: resistance.confidence,
          varieties: varieties,
          treatment: treatments,
          iotTrigger: iotTriggers,
          source: resistance.source
        } as edge
      `;
      params = { crop };
    } else {
      // Get edges for a specific variety
      query = `
        MATCH (variety:Variety {name: $variety, crop: $crop})
        MATCH (variety)-[carries:CARRIES]->(g:Gene)
        MATCH (g)-[resistance:CONFERS_RESISTANCE_TO]->(d:Disease)
        MATCH (d)-[:TREATED_BY]->(t:Treatment)
        WITH
          g,
          d,
          resistance,
          collect(DISTINCT t.action) as treatments,
          collect(DISTINCT t.iot_trigger) as iotTriggers
        RETURN {
          gene: g.id,
          chromosome: g.chromosome,
          allele: g.allele,
          resistanceType: g.resistance_type,
          disease: d.name,
          pathogen: d.pathogen,
          confidence: resistance.confidence,
          varieties: [$variety],
          treatment: treatments,
          iotTrigger: iotTriggers,
          source: resistance.source
        } as edge
      `;
      params = { variety, crop };
    }

    const result = await queryNeo4j(
      env.NEO4J_URI,
      env.NEO4J_USER,
      env.NEO4J_PASSWORD,
      env.NEO4J_DATABASE,
      query,
      params,
    );

    // Extract edges from Neo4j response
    const edges = (result.data?.values || []).map((row) => normalizeEdge(row[0]));

    return json(200, {
      edges,
      query: { crop, variety },
      count: edges.length,
    });
  } catch (error) {
    console.error("Query error:", error);
    return json(500, {
      error: error.message || "Database query failed",
    });
  }
}
