// AgriHub KB — frontend controller (rebuilt against the Postgres/Supabase KG, 2026-09-26)

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

const tabButtons = document.querySelectorAll(".tab-btn");
const tabPanels = { browse: document.getElementById("tab-browse"), triggers: document.getElementById("tab-triggers") };

for (const btn of tabButtons) {
  btn.addEventListener("click", () => {
    for (const b of tabButtons) b.setAttribute("aria-selected", String(b === btn));
    for (const [name, panel] of Object.entries(tabPanels)) {
      panel.dataset.active = String(name === btn.dataset.tab);
    }
  });
}

// ---------------------------------------------------------------------------
// Stats bar
// ---------------------------------------------------------------------------

async function loadStats() {
  const statsBar = document.getElementById("statsBar");
  try {
    const response = await fetch("/api/stats");
    if (!response.ok) return; // stats are a nice-to-have; fail silently
    const data = await response.json();
    document.getElementById("statEdges").textContent = data.edges ?? "—";
    document.getElementById("statGenes").textContent = data.genes ?? "—";
    document.getElementById("statDiseases").textContent = data.diseases ?? "—";
    document.getElementById("statVarieties").textContent = data.varieties ?? "—";
    document.getElementById("statCrops").textContent = data.crops ?? "—";
    statsBar.hidden = false;
  } catch {
    // If /api/stats isn't reachable, the bar stays hidden — no error shown.
  }
}

// ---------------------------------------------------------------------------
// Shared: variety loader (used by both tabs' crop/variety selects)
// ---------------------------------------------------------------------------

async function loadVarietiesInto(cropSelect, varietySelect, statusSetter) {
  const previousSelection = varietySelect.value;
  varietySelect.disabled = true;
  varietySelect.replaceChildren(Object.assign(document.createElement("option"), { value: "__all__", textContent: "Loading varieties..." }));
  statusSetter?.("Loading varieties...", "loading");

  try {
    const response = await fetch(`/api/varieties?crop=${encodeURIComponent(cropSelect.value)}`);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Could not load varieties");

    const options = [{ label: "All varieties", value: "__all__" }, ...payload.varieties.map((v) => ({ label: v.name, value: v.id }))];
    varietySelect.replaceChildren(
      ...options.map((opt) => Object.assign(document.createElement("option"), { value: opt.value, textContent: opt.label })),
    );
    const values = options.map((o) => o.value);
    varietySelect.value = values.includes(previousSelection) ? previousSelection : "__all__";
    statusSetter?.(`${payload.count || 0} variet${payload.count === 1 ? "y" : "ies"}`, "ready");
  } catch (error) {
    varietySelect.replaceChildren(Object.assign(document.createElement("option"), { value: "__all__", textContent: "All varieties" }));
    statusSetter?.("Error loading varieties", "error");
  } finally {
    varietySelect.disabled = false;
  }
}

// ---------------------------------------------------------------------------
// TAB: Browse the graph
// ---------------------------------------------------------------------------

const cropSelect = document.getElementById("cropSelect");
const varietySelect = document.getElementById("varietySelect");
const searchButton = document.getElementById("searchButton");
const reactionStatusText = document.getElementById("reactionStatusText");
const geneStatusText = document.getElementById("geneStatusText");
const reactionList = document.getElementById("reactionList");
const geneList = document.getElementById("geneList");

function setStatus(el, text, state = "idle") {
  el.textContent = text;
  el.dataset.state = state;
}

function renderReactions(reactions, varietySelected) {
  reactionList.innerHTML = "";
  if (!varietySelected) {
    reactionList.innerHTML = `<div class="edge-card"><p class="edge-meta">Pick a specific variety to see its documented reactions.</p></div>`;
    return;
  }
  if (!reactions.length) {
    reactionList.innerHTML = `<div class="edge-card"><p class="edge-meta">No VARIETY_REACTION claims loaded for this variety.</p></div>`;
    return;
  }
  for (const r of reactions) {
    const card = document.createElement("article");
    card.className = "edge-card";
    card.innerHTML = `
      <h3>${r.disease_name}</h3>
      <p class="edge-meta">Reaction: <strong>${r.reaction ?? "n/a"}</strong> &nbsp;|&nbsp; Stage: ${r.stage ?? "n/a"}</p>
    `;
    reactionList.appendChild(card);
  }
}

function renderGenes(genes) {
  geneList.innerHTML = "";
  if (!genes.length) {
    geneList.innerHTML = `<div class="edge-card"><p class="edge-meta">No gene resistance claims for this crop.</p></div>`;
    return;
  }
  for (const g of genes) {
    const card = document.createElement("article");
    card.className = "edge-card";
    const clonedBadge = g.cloned ? `<span class="confidence-badge" data-level="High">cloned</span>` : "";
    card.innerHTML = `
      <h3>${g.gene_name} → ${g.disease_name} ${clonedBadge}</h3>
      <p class="edge-meta">Chromosome: ${g.chromosome ?? "n/a"} &nbsp;|&nbsp; Type: ${g.resistance_type ?? "n/a"}</p>
      <p class="edge-meta">${g.gene_class ?? ""}</p>
      ${g.spectrum ? `<p class="edge-meta">Spectrum: ${g.spectrum}</p>` : ""}
    `;
    geneList.appendChild(card);
  }
}

async function runQuery() {
  setStatus(geneStatusText, "Loading...", "loading");
  const varietySelected = varietySelect.value !== "__all__";
  setStatus(reactionStatusText, varietySelected ? "Loading..." : "Select a variety", varietySelected ? "loading" : "idle");

  try {
    const response = await fetch("/api/query", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ crop: cropSelect.value, variety: varietySelect.value }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Query failed");

    renderGenes(payload.geneResistance || []);
    setStatus(geneStatusText, `${payload.counts.geneResistance} gene claim(s)`, "ready");

    renderReactions(payload.varietyReactions || [], varietySelected);
    if (varietySelected) {
      setStatus(reactionStatusText, `${payload.counts.varietyReactions} reaction(s)`, "ready");
    }
  } catch (error) {
    setStatus(geneStatusText, "Error", "error");
    geneList.innerHTML = `<div class="edge-card edge-card-error"><h3>Query failed</h3><p class="edge-meta">${error.message}</p></div>`;
  }
}

cropSelect.addEventListener("change", () => loadVarietiesInto(cropSelect, varietySelect, (t, s) => setStatus(reactionStatusText, t, s)));
searchButton.addEventListener("click", runQuery);

// ---------------------------------------------------------------------------
// TAB: Check sensor readings
// ---------------------------------------------------------------------------

const triggerCropSelect = document.getElementById("triggerCropSelect");
const triggerVarietySelect = document.getElementById("triggerVarietySelect");
const checkTriggersButton = document.getElementById("checkTriggersButton");
const triggerStatusText = document.getElementById("triggerStatusText");
const triggerList = document.getElementById("triggerList");

const SENSOR_FIELDS = ["air_temp_c", "air_rh", "soil_temp_c", "soil_moisture_vwc", "dew_point_c", "rh_ge_80_h"];

function collectReadings() {
  const readings = {};
  for (const field of SENSOR_FIELDS) {
    const input = document.getElementById(`reading-${field}`);
    if (input.value !== "") readings[field] = Number(input.value);
  }
  return readings;
}

function conditionLine(c) {
  const bound = [c.min !== null && c.min !== undefined ? `≥ ${c.min}` : null, c.max !== null && c.max !== undefined ? `≤ ${c.max}` : null]
    .filter(Boolean)
    .join(" and ");
  const got = c.status === "missing" ? "not entered" : c.value;
  const icon = c.status === "met" ? "✅" : c.status === "not_met" ? "❌" : "❓";
  return `<li>${icon} ${c.variable} (${c.aggregation} over ${c.window_h}h): needs ${bound} — got ${got}</li>`;
}

function renderTriggers(results) {
  triggerList.innerHTML = "";
  if (!results.length) {
    triggerList.innerHTML = `<div class="edge-card"><p class="edge-meta">No env-trigger claims loaded for this crop yet.</p></div>`;
    return;
  }

  const statusLabel = { fired: "TRIGGER FIRED", not_met: "Conditions not met", insufficient_data: "Enter more readings" };
  const statusLevel = { fired: "Very High", not_met: "Medium", insufficient_data: "Medium" };

  for (const r of results) {
    const card = document.createElement("article");
    card.className = "edge-card";
    if (r.status === "fired") card.classList.add("edge-card-fired");

    const advisoryLines = r.advisories.length
      ? r.advisories.map((a) => `<p class="edge-meta">Advisory (${a.actionType}): ${a.name}</p>`).join("")
      : `<p class="edge-meta">No DISEASE_MANAGED_BY advisory loaded for this disease yet.</p>`;

    const reactionLine = r.varietyReaction
      ? `<p class="edge-meta">Selected variety's documented reaction: <strong>${r.varietyReaction.reaction}</strong> (${r.varietyReaction.stage})</p>`
      : "";

    card.innerHTML = `
      <h3>${r.diseaseName} <span class="confidence-badge" data-level="${statusLevel[r.status]}">${statusLabel[r.status]}</span></h3>
      <p class="edge-meta">${r.triggerName}</p>
      <p class="edge-meta">Growth-stage window: BBCH ${r.bbchFrom}–${r.bbchTo} &nbsp;|&nbsp; Phase: ${r.phase}</p>
      <ul class="condition-list">${r.conditions.map(conditionLine).join("")}</ul>
      ${r.status === "fired" ? advisoryLines : ""}
      ${reactionLine}
    `;
    triggerList.appendChild(card);
  }
}

async function checkTriggers() {
  setStatus(triggerStatusText, "Checking...", "loading");
  try {
    const response = await fetch("/api/triggers", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        crop: triggerCropSelect.value,
        variety: triggerVarietySelect.value,
        readings: collectReadings(),
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Query failed");

    renderTriggers(payload.results || []);
    setStatus(triggerStatusText, `${payload.counts.fired} fired / ${payload.counts.total} checked`, "ready");
  } catch (error) {
    setStatus(triggerStatusText, "Error", "error");
    triggerList.innerHTML = `<div class="edge-card edge-card-error"><h3>Check failed</h3><p class="edge-meta">${error.message}</p></div>`;
  }
}

triggerCropSelect.addEventListener("change", () => loadVarietiesInto(triggerCropSelect, triggerVarietySelect));
checkTriggersButton.addEventListener("click", checkTriggers);

// ---------------------------------------------------------------------------
// Initialise
// ---------------------------------------------------------------------------

loadVarietiesInto(cropSelect, varietySelect, (t, s) => setStatus(reactionStatusText, t, s));
loadVarietiesInto(triggerCropSelect, triggerVarietySelect);
loadStats();
