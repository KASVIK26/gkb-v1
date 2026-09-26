/**
 * POST /api/triggers   { crop, variety, readings: { air_temp_c: 12, air_rh: 95, ... } }
 *
 * Checks submitted sensor readings against every DISEASE_ENV_TRIGGER for the crop and reports
 * which ones fire, with the matched disease's DISEASE_MANAGED_BY advisories and (if a specific
 * variety was selected) that variety's own documented VARIETY_REACTION to the same disease.
 *
 * SCOPE NOTE, load-bearing: this is a single-snapshot comparison against whatever numbers are
 * typed into the form -- it does NOT implement the real windowed/aggregated model each trigger's
 * own conditions (aggregation: mean/min/max/sum/count, window_h) describe. A real risk engine
 * (RESEARCH_ROADMAP.md Phase 11) would aggregate a time series of sensor readings over that
 * window before comparing; this demo compares the raw submitted value directly, on the
 * (unstated-to-the-user-if-not-explained) assumption that the number given already represents
 * that aggregate. Good enough to exercise the KG's real trigger/advisory data interactively; not
 * a substitute for the real engine.
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

// Evaluate one {variable, min, max} condition against the submitted readings.
function evaluateCondition(condition, readings) {
  const value = readings[condition.variable];
  if (value === undefined || value === null || value === "") {
    return { ...condition, value: null, status: "missing" };
  }
  const numeric = Number(value);
  const min = condition.min ?? -Infinity;
  const max = condition.max ?? Infinity;
  const met = numeric >= min && numeric <= max;
  return { ...condition, value: numeric, status: met ? "met" : "not_met" };
}

function evaluateTrigger(trigger, readings) {
  const conditions = (trigger.conditions || []).map((c) => evaluateCondition(c, readings));
  let status;
  if (conditions.some((c) => c.status === "not_met")) {
    status = "not_met";
  } else if (conditions.some((c) => c.status === "missing")) {
    status = "insufficient_data";
  } else {
    status = "fired";
  }
  return { ...trigger, conditions, status };
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
  const readings = payload.readings && typeof payload.readings === "object" ? payload.readings : {};

  if (!crop) {
    return json(400, { error: "Missing required field: crop." });
  }

  if (!env?.SUPABASE_URL || !env?.SUPABASE_PUBLISHABLE_KEY) {
    return json(503, { error: "Supabase credentials are not configured for this environment." });
  }

  try {
    const triggerRows = await supabaseGet(
      env,
      "kg_disease_triggers",
      new URLSearchParams({ crop: `eq.${crop}`, order: "disease_name.asc" }),
    );

    const diseaseIds = [...new Set(triggerRows.map((t) => t.disease_id))];
    const advisoryRows = diseaseIds.length
      ? await supabaseGet(
          env,
          "kg_disease_advisories",
          new URLSearchParams({ disease_id: `in.(${diseaseIds.join(",")})` }),
        )
      : [];

    let reactionByDisease = {};
    if (variety !== "__all__") {
      const reactions = await supabaseGet(
        env,
        "kg_variety_reactions",
        new URLSearchParams({ variety_id: `eq.${variety}` }),
      );
      reactionByDisease = Object.fromEntries(reactions.map((r) => [r.disease_id, r]));
    }

    const evaluated = triggerRows.map((t) => evaluateTrigger(t, readings));

    const results = evaluated.map((t) => ({
      diseaseId: t.disease_id,
      diseaseName: t.disease_name,
      triggerId: t.trigger_id,
      triggerName: t.trigger_name,
      phase: t.phase,
      bbchFrom: t.bbch_from,
      bbchTo: t.bbch_to,
      status: t.status,
      conditions: t.conditions,
      advisories: advisoryRows
        .filter((a) => a.disease_id === t.disease_id)
        .map((a) => ({ name: a.advisory_name, actionType: a.action_type })),
      varietyReaction: reactionByDisease[t.disease_id]
        ? { reaction: reactionByDisease[t.disease_id].reaction, stage: reactionByDisease[t.disease_id].stage }
        : null,
    }));

    return json(200, {
      query: { crop, variety, readings },
      results,
      counts: {
        total: results.length,
        fired: results.filter((r) => r.status === "fired").length,
        insufficientData: results.filter((r) => r.status === "insufficient_data").length,
      },
    });
  } catch (error) {
    console.error("Triggers query error:", error);
    return json(500, { error: error.message || "Database query failed" });
  }
}
