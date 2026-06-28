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

async function queryNeo4j(uri, user, password, database, query, params = {}) {
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
}

export async function onRequestGet({ request, env }) {
  const url = new URL(request.url);
  const crop = String(url.searchParams.get("crop") || "").trim().toLowerCase();

  if (!crop) {
    return json(400, { error: "Missing required query parameter: crop." });
  }

  if (!env?.NEO4J_URI || !env?.NEO4J_USER || !env?.NEO4J_PASSWORD) {
    return json(503, {
      error: "Neo4j credentials are not configured for this environment.",
    });
  }

  try {
    const result = await queryNeo4j(
      env.NEO4J_URI,
      env.NEO4J_USER,
      env.NEO4J_PASSWORD,
      env.NEO4J_DATABASE,
      `
        MATCH (crop:Crop {name: $crop})
        MATCH (crop)<-[:BELONGS_TO]-(v:Variety)
        RETURN DISTINCT v.name as variety
        ORDER BY toLower(variety)
      `,
      { crop },
    );

    const varieties = (result.data?.values || []).map((row) => row[0]);

    return json(200, {
      crop,
      varieties,
      count: varieties.length,
    });
  } catch (error) {
    console.error("Varieties query error:", error);
    return json(500, {
      error: error.message || "Database query failed",
    });
  }
}
