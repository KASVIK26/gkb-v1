// AgriHub KB — frontend controller (rebuilt against the Postgres/Supabase KG, 2026-09-26)

import { initTour } from "./tour.js";

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

const tabButtons = document.querySelectorAll(".tab-btn");
const tabPanels = {
  browse: document.getElementById("tab-browse"),
  triggers: document.getElementById("tab-triggers"),
  graph: document.getElementById("tab-graph"),
};

let graphInitialized = false;
let graphLoad = null;

// Resolves once /api/graph has loaded and the first render is done -- the guided tour waits on it.
function whenGraphReady() {
  return graphLoad ?? Promise.resolve();
}

function showTab(name) {
  for (const b of tabButtons) b.setAttribute("aria-selected", String(b.dataset.tab === name));
  for (const [tabName, panel] of Object.entries(tabPanels)) {
    panel.dataset.active = String(tabName === name);
  }
  if (name === "graph") {
    if (!graphInitialized) {
      graphInitialized = true;
      graphLoad = loadGraphData();
    } else if (cy) {
      // The canvas was display:none while hidden -- cytoscape needs an explicit resize/fit.
      cy.resize();
      cy.fit();
    }
  }
}

for (const btn of tabButtons) {
  btn.addEventListener("click", () => showTab(btn.dataset.tab));
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
// Shared: escaping, confidence chips and the evidence behind a claim
// ---------------------------------------------------------------------------

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

// Tier = strength of the cited evidence, combined across independent sources (curator/graph/scoring.py).
const TIER_MEANING = {
  A: "Strong evidence (validated, official or multi-location)",
  B: "Good evidence",
  C: "Moderate evidence",
  D: "Weak evidence (for example a single statement in a review)",
};

const METHOD_LABEL = {
  official_document: "Official release document",
  cloned_validated: "Cloned and functionally validated gene",
  diagnostic_marker: "Diagnostic marker",
  linked_marker: "Closely linked molecular marker",
  sequence_haplotype: "Sequence haplotype",
  field_multi_env: "Multi-location field trials",
  qtl_mapping: "QTL mapping",
  gwas: "GWAS association",
  field_single_env: "Single-environment field trial",
  controlled_env: "Controlled-environment study",
  postulation_pedigree: "Pedigree or postulation",
  review_statement: "Statement in a review article",
  computational: "Computational prediction",
  curator_assertion: "Curated vocabulary entry",
};

const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

// `item` may be a row from any of the public views: it carries tier, score, n_sources, conflict.
function tierChip(item) {
  if (!item || !item.tier) return "";
  const score = typeof item.score === "number" ? ` (score ${item.score.toFixed(2)})` : "";
  const title = `${TIER_MEANING[item.tier] ?? ""}${score}${item.conflict ? ". Conflicting reports exist for this claim." : ""}`;
  const sources = item.n_sources ? ` · ${plural(item.n_sources, "source")}` : "";
  return `<span class="tier-chip" data-tier="${esc(item.tier)}" title="${esc(title)}"><span class="tier-swatch" aria-hidden="true"></span>Tier ${esc(item.tier)}${sources}${item.conflict ? " · conflict" : ""}</span>`;
}

function evidenceHtml(rows) {
  if (!rows.length) return `<p class="edge-meta">No evidence rows are published for this claim.</p>`;
  return `<ul class="evidence-list">${rows
    .map((r) => {
      const where = [r.source_venue, r.source_year].filter(Boolean).join(", ");
      const title = r.source_url
        ? `<a href="${esc(r.source_url)}" target="_blank" rel="noopener noreferrer">${esc(r.source_title)}</a>`
        : esc(r.source_title);
      return `<li><strong>${title}</strong>${where ? ` <span class="edge-meta">(${esc(where)})</span>` : ""}<br>
        <span class="edge-meta">${esc(METHOD_LABEL[r.method] ?? r.method)} · weight ${Number(r.weight).toFixed(2)}${r.locator ? ` · ${esc(r.locator)}` : ""}${r.human_reviewed ? " · human-reviewed" : ""}</span></li>`;
    })
    .join("")}</ul>`;
}

// The "do this" facts of an advisory, limited to what its source actually states.
function advisoryFacts(p) {
  const rows = [
    ["Product", p.active_ingredient],
    ["Rate", p.dose],
    ["When", p.timing],
    ["Crop stage", p.bbch_from != null && p.bbch_to != null ? `BBCH ${p.bbch_from}–${p.bbch_to}` : null],
    ["Applies to", p.region],
  ].filter(([, value]) => value);
  if (!rows.length) return "";
  return `<dl class="advisory-facts">${rows.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join("")}</dl>`;
}

// The numeric conditions of a weather trigger, e.g. "soil_temp_c 22–26 (mean over 24 h)".
function triggerFacts(p) {
  const conditions = Array.isArray(p.conditions) ? p.conditions : [];
  if (!conditions.length) return "";
  const bound = (c) => [c.min != null ? `≥ ${c.min}` : null, c.max != null ? `≤ ${c.max}` : null].filter(Boolean).join(" and ");
  const rows = conditions.map((c) => `<div><dt>${esc(c.variable)}</dt><dd>${esc(bound(c))} (${esc(c.aggregation)} over ${esc(c.window_h)} h)</dd></div>`);
  if (p.bbch_from != null) rows.push(`<div><dt>Crop stage</dt><dd>BBCH ${esc(p.bbch_from)}–${esc(p.bbch_to)}${p.phase ? ` · ${esc(p.phase)}` : ""}</dd></div>`);
  return `<dl class="advisory-facts">${rows.join("")}</dl>`;
}

const evidenceCache = new Map();

async function fetchEvidence(claimId) {
  if (!evidenceCache.has(claimId)) {
    const response = await fetch(`/api/evidence?claim_id=${encodeURIComponent(claimId)}`);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Could not load the evidence");
    evidenceCache.set(claimId, payload.evidence);
  }
  return evidenceCache.get(claimId);
}

async function renderEvidenceInto(container, claimId) {
  container.innerHTML = `<p class="edge-meta">Loading the sources…</p>`;
  try {
    container.innerHTML = evidenceHtml(await fetchEvidence(claimId));
  } catch (error) {
    container.innerHTML = `<p class="edge-meta">Could not load the evidence: ${esc(error.message)}</p>`;
  }
}

// A collapsed "Show evidence" row on a Browse card; the sources are fetched the first time it opens.
function attachEvidence(card, claimId) {
  if (!claimId) return;
  const details = document.createElement("details");
  details.className = "evidence-details";
  details.innerHTML = `<summary>Show evidence</summary><div class="evidence-body"></div>`;
  details.addEventListener("toggle", () => {
    const body = details.querySelector(".evidence-body");
    if (details.open && !body.dataset.loaded) {
      body.dataset.loaded = "1";
      renderEvidenceInto(body, claimId);
    }
  });
  card.appendChild(details);
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
      <h3>${esc(r.disease_name)} ${tierChip(r)}</h3>
      <p class="edge-meta">Reaction: <strong>${esc(r.reaction ?? "n/a")}</strong> &nbsp;|&nbsp; Stage: ${esc(r.stage ?? "n/a")}</p>
    `;
    attachEvidence(card, r.claim_id);
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
      <h3>${esc(g.gene_name)} → ${esc(g.disease_name)} ${clonedBadge} ${tierChip(g)}</h3>
      <p class="edge-meta">Chromosome: ${g.chromosome ?? "n/a"} &nbsp;|&nbsp; Type: ${g.resistance_type ?? "n/a"}</p>
      <p class="edge-meta">${g.gene_class ?? ""}</p>
      ${g.spectrum ? `<p class="edge-meta">Spectrum: ${esc(g.spectrum)}</p>` : ""}
    `;
    attachEvidence(card, g.claim_id);
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
      ? r.advisories
          .map(
            (a) =>
              `<p class="edge-meta">Advisory (${esc(a.actionType)}): ${esc(a.name)} ${tierChip({ tier: a.tier, score: a.score, n_sources: a.nSources })}</p>` +
              advisoryFacts({
                active_ingredient: a.activeIngredient, dose: a.dose, timing: a.timing,
                bbch_from: a.bbchFrom, bbch_to: a.bbchTo, region: a.region,
              }),
          )
          .join("")
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
// TAB: Visualize the graph
// ---------------------------------------------------------------------------

const graphCropSelect = document.getElementById("graphCropSelect");
const graphDiseaseSelect = document.getElementById("graphDiseaseSelect");
const graphClaimTypesContainer = document.getElementById("graphClaimTypes");
const graphStatusText = document.getElementById("graphStatusText");
const graphCanvas = document.getElementById("graphCanvas");
const graphLegend = document.getElementById("graphLegend");
const graphDetail = document.getElementById("graphDetail");
const graphTooltip = document.getElementById("graphTooltip");
const graphZoomIn = document.getElementById("graphZoomIn");
const graphZoomOut = document.getElementById("graphZoomOut");
const graphZoomFit = document.getElementById("graphZoomFit");
const graphPresets = document.getElementById("graphPresets");
const graphConfidence = document.getElementById("graphConfidence");
const graphEmpty = document.getElementById("graphEmpty");

function darken(hex, factor) {
  const n = parseInt(hex.slice(1), 16);
  const channels = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => Math.round(v * factor));
  return `#${channels.map((v) => v.toString(16).padStart(2, "0")).join("")}`;
}

// Colour AND shape encode entity type: 11 types cannot be told apart by hue alone for everyone.
// Hues are the dataviz-validated palette (Disease a deeper red); every type pair that shares an edge
// in the live graph measured >= 18.6 colour-blind / 19.6 normal-vision distance (see PHASES.md).
const NODE_STYLE = {
  Crop: { name: "Crop", color: "#2b2a27", shape: "rectangle", size: 30, anchor: true, blurb: "A crop species covered here." },
  Disease: { name: "Disease", color: "#a61b2a", shape: "octagon", size: 26, anchor: true, blurb: "A crop disease; most claims link to it." },
  Pathogen: { name: "Pathogen", color: "#eb6834", shape: "triangle", size: 22, blurb: "The organism causing a disease." },
  Pathotype: { name: "Pathotype", color: "#eb6834", shape: "pentagon", size: 20, blurb: "A race or strain of a pathogen." },
  Variety: { name: "Variety", color: "#2a78d6", shape: "ellipse", size: 13, blurb: "A named cultivar." },
  Gene: { name: "Gene", color: "#4a3aa7", shape: "diamond", size: 22, blurb: "A gene that confers resistance." },
  RefGene: { name: "Reference gene", color: "#6b7785", shape: "star", size: 24, blurb: "Where a gene sits in the reference genome." },
  Marker: { name: "Marker", color: "#4a3aa7", shape: "round-diamond", size: 18, blurb: "A DNA marker used to track a resistance gene." },
  QTL: { name: "QTL", color: "#1baf7a", shape: "hexagon", size: 22, blurb: "A genome region linked to resistance." },
  EnvTrigger: { name: "Weather trigger", color: "#eda100", shape: "rhomboid", size: 22, blurb: "Weather that favours infection." },
  Advisory: { name: "Advisory", color: "#e87ba4", shape: "round-rectangle", size: 22, blurb: "A recommended management practice." },
  AgroZone: { name: "Growing zone", color: "#008300", shape: "cut-rectangle", size: 20, blurb: "A region a variety suits." },
};
const LEGEND_ORDER = Object.keys(NODE_STYLE);
const styleOf = (type) => NODE_STYLE[type] || { name: type, color: "#6b7785", shape: "ellipse", size: 16, blurb: "" };

// Plain-language meaning of each relationship. `verb` reads subject -> object; `out`/`inn` are the
// headings used in the detail panel from the subject's / object's point of view.
const CLAIM_INFO = {
  VARIETY_REACTION: { from: "Variety", to: "Disease", verb: "has a documented reaction to", out: "Documented reactions", inn: "Varieties with a documented reaction" },
  VARIETY_RECOMMENDED_FOR_ZONE: { from: "Variety", to: "AgroZone", verb: "is recommended for", out: "Recommended for zones", inn: "Recommended varieties" },
  GENE_CONFERS_RESISTANCE: { from: "Gene", to: "Disease", verb: "confers resistance to", out: "Confers resistance to", inn: "Resistance genes" },
  DISEASE_MANAGED_BY: { from: "Disease", to: "Advisory", verb: "is managed by", out: "Managed by", inn: "Diseases it helps manage" },
  DISEASE_ENV_TRIGGER: { from: "Disease", to: "EnvTrigger", verb: "is favoured by", out: "Favoured by", inn: "Diseases it favours" },
  DISEASE_CAUSED_BY: { from: "Disease", to: "Pathogen", verb: "is caused by", out: "Caused by", inn: "Diseases it causes" },
  GENE_PATHOTYPE_INTERACTION: { from: "Gene", to: "Pathotype", verb: "interacts with", out: "Interacts with pathotype", inn: "Interacting genes" },
  PATHOTYPE_VARIANT_OF: { from: "Pathotype", to: "Pathogen", verb: "is a variant of", out: "Variant of", inn: "Known variants" },
  QTL_ASSOCIATION: { from: "QTL", to: "Disease", verb: "is associated with", out: "Associated with", inn: "Associated QTLs" },
  GENE_LOCATED_AT: { from: "Gene", to: "RefGene", verb: "is located at", out: "Located at", inn: "Genes located here" },
};
function claimInfo(claimType) {
  const fallback = claimType.replaceAll("_", " ").toLowerCase();
  return CLAIM_INFO[claimType] || { from: null, to: null, verb: fallback, out: fallback, inn: fallback };
}
function claimLabel(claimType) {
  const info = claimInfo(claimType);
  if (!info.from) return info.verb;
  return `${styleOf(info.from).name} ${info.verb} ${styleOf(info.to).name.toLowerCase()}`;
}

// Questions a visitor is likely to have; each one just selects the matching relationship types.
const GRAPH_PRESETS = [
  { id: "genes", label: "Which genes confer resistance?", types: ["GENE_CONFERS_RESISTANCE"] },
  { id: "varieties", label: "Which varieties resist which diseases?", types: ["VARIETY_REACTION"] },
  { id: "profile", label: "How is each disease caused, triggered and managed?", types: ["DISEASE_CAUSED_BY", "DISEASE_ENV_TRIGGER", "DISEASE_MANAGED_BY"] },
  { id: "zones", label: "Where is each variety recommended?", types: ["VARIETY_RECOMMENDED_FOR_ZONE"] },
  { id: "all", label: "Show everything", types: null },
];

// Fetched once from /api/graph and kept for the life of the page -- every filter change re-derives
// the visible subgraph from this cache, so filtering is instant and never hits the network again.
let graphCache = null;
let cy = null; // the cytoscape instance, created lazily on first activation of this tab
let activePreset = "all";
const hiddenTypes = new Set();

async function loadGraphData() {
  setStatus(graphStatusText, "Loading graph...", "loading");
  try {
    const response = await fetch("/api/graph");
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Could not load the graph");
    graphCache = payload;
    populateGraphFilters(payload);
    renderGraphPresets();
    renderGraphConfidence(payload);
    renderGraph();
  } catch (error) {
    setStatus(graphStatusText, "Error", "error");
    graphCanvas.innerHTML = `<div class="edge-card edge-card-error"><h3>Could not load the graph</h3><p class="edge-meta">${esc(error.message)}</p></div>`;
  }
}

function populateGraphFilters(payload) {
  const counts = new Map();
  for (const edge of payload.edges) counts.set(edge.claim_type, (counts.get(edge.claim_type) || 0) + 1);
  const claimTypes = [...counts.keys()].sort();
  graphClaimTypesContainer.replaceChildren(
    ...claimTypes.map((type) => {
      const label = document.createElement("label");
      label.className = "graph-checkbox";
      label.innerHTML = `<input type="checkbox" value="${esc(type)}" checked /> ${esc(claimLabel(type))} <span class="graph-count">${counts.get(type)}</span>`;
      label.querySelector("input").addEventListener("change", () => {
        activePreset = null;
        renderGraphPresets();
        renderGraph();
      });
      return label;
    }),
  );
  updateDiseaseOptions();
}

function renderGraphPresets() {
  graphPresets.replaceChildren(
    ...GRAPH_PRESETS.map((preset) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "graph-preset";
      button.textContent = preset.label;
      button.setAttribute("aria-pressed", String(preset.id === activePreset));
      button.addEventListener("click", () => applyPreset(preset));
      return button;
    }),
  );
}

function applyPreset(preset) {
  activePreset = preset.id;
  hiddenTypes.clear();
  for (const box of graphClaimTypesContainer.querySelectorAll("input")) {
    box.checked = !preset.types || preset.types.includes(box.value);
  }
  renderGraphPresets();
  renderGraph();
}

function renderGraphConfidence(payload) {
  const total = payload.edges.length;
  const tiers = { A: 0, B: 0, C: 0, D: 0 };
  for (const edge of payload.edges) if (edge.tier in tiers) tiers[edge.tier] += 1;
  const tiered = Object.values(tiers).reduce((a, b) => a + b, 0);
  const reviewed = payload.edges.filter((e) => e.status && e.status !== "unreviewed").length;
  const single = payload.edges.filter((e) => e.n_sources === 1).length;
  const conflicts = payload.edges.filter((e) => e.conflict).length;

  if (!tiered) {
    graphConfidence.innerHTML = `<strong>About confidence:</strong> every one of these ${total} claims links to a cited source, but confidence tiers are <em>not computed in this release</em>.`;
    return;
  }
  graphConfidence.innerHTML =
    `<strong>About confidence:</strong> each claim has a tier from A (strongest) to D (weakest) — the strength of its cited evidence, combined across independent sources. ` +
    `Here: ${Object.entries(tiers).map(([t, n]) => `<strong>${t}</strong> ${n}`).join(" · ")}. ` +
    `${single} of ${total} claims rest on a single source, so a tier describes how good that one source is, not independent confirmation; ` +
    `${reviewed ? `${reviewed} have` : "none have"} been human-reviewed${conflicts ? ` and ${conflicts} have conflicting reports` : ""}. ` +
    `<em>Click any line to see its sources.</em>`;
}

function updateDiseaseOptions() {
  if (!graphCache) return;
  const crop = graphCropSelect.value;
  const diseases = graphCache.nodes
    .filter((n) => n.type === "Disease" && (crop === "__all__" || n.crop === crop))
    .sort((a, b) => a.name.localeCompare(b.name));
  const previous = graphDiseaseSelect.value;
  graphDiseaseSelect.replaceChildren(
    Object.assign(document.createElement("option"), { value: "__all__", textContent: "All diseases" }),
    ...diseases.map((d) => Object.assign(document.createElement("option"), { value: d.id, textContent: d.name })),
  );
  const values = ["__all__", ...diseases.map((d) => d.id)];
  graphDiseaseSelect.value = values.includes(previous) ? previous : "__all__";
}

// `applyHidden: false` gives the set the legend should list (so a hidden type stays clickable).
function filteredGraph({ applyHidden = true } = {}) {
  if (!graphCache) return { nodes: [], edges: [] };
  const crop = graphCropSelect.value;
  const disease = graphDiseaseSelect.value;
  const checkedTypes = new Set(
    [...graphClaimTypesContainer.querySelectorAll("input:checked")].map((cb) => cb.value),
  );

  let edges = graphCache.edges.filter((e) => checkedTypes.has(e.claim_type));
  if (crop !== "__all__") {
    edges = edges.filter((e) => e.subject_crop === crop || e.object_crop === crop);
  }
  if (disease !== "__all__") {
    edges = edges.filter((e) => e.subject_id === disease || e.object_id === disease);
  }

  const nodeIds = new Set(edges.flatMap((e) => [e.subject_id, e.object_id]));
  let nodes = graphCache.nodes.filter((n) => nodeIds.has(n.id));
  if (applyHidden && hiddenTypes.size) {
    nodes = nodes.filter((n) => !hiddenTypes.has(n.type));
    const kept = new Set(nodes.map((n) => n.id));
    edges = edges.filter((e) => kept.has(e.subject_id) && kept.has(e.object_id));
    const connected = new Set(edges.flatMap((e) => [e.subject_id, e.object_id]));
    nodes = nodes.filter((n) => connected.has(n.id));
  }
  return { nodes, edges };
}

function ngon(sides, startDeg, radius = 8.6) {
  return Array.from({ length: sides }, (_, i) => {
    const angle = ((startDeg + (360 / sides) * i) * Math.PI) / 180;
    return `${(10 + radius * Math.cos(angle)).toFixed(1)},${(10 + radius * Math.sin(angle)).toFixed(1)}`;
  }).join(" ");
}

function starPoints() {
  return Array.from({ length: 10 }, (_, i) => {
    const angle = ((-90 + 36 * i) * Math.PI) / 180;
    const radius = i % 2 === 0 ? 9.2 : 4.2;
    return `${(10 + radius * Math.cos(angle)).toFixed(1)},${(10 + radius * Math.sin(angle)).toFixed(1)}`;
  }).join(" ");
}

// Legend swatch drawn in the same shape the node has on the canvas.
function shapeSvg(shape, color) {
  const paint = `fill="${color}" stroke="${darken(color, 0.6)}" stroke-width="1.4" stroke-linejoin="round"`;
  const polygon = (points) => `<polygon points="${points}" ${paint}/>`;
  const body = {
    ellipse: `<circle cx="10" cy="10" r="7.5" ${paint}/>`,
    rectangle: `<rect x="3" y="4" width="14" height="12" ${paint}/>`,
    "round-rectangle": `<rect x="3" y="4" width="14" height="12" rx="3.5" ${paint}/>`,
    "cut-rectangle": polygon("5,3.5 15,3.5 18,6.5 18,13.5 15,16.5 5,16.5 2,13.5 2,6.5"),
    diamond: polygon("10,1.5 18.5,10 10,18.5 1.5,10"),
    "round-diamond": polygon("10,3 17,10 10,17 3,10"),
    hexagon: polygon(ngon(6, 0)),
    octagon: polygon(ngon(8, 22.5)),
    pentagon: polygon(ngon(5, -90)),
    triangle: polygon("10,2.5 18,16.5 2,16.5"),
    star: polygon(starPoints()),
    rhomboid: polygon("2,3.5 12.5,3.5 18,16.5 7.5,16.5"),
  }[shape] || `<circle cx="10" cy="10" r="7.5" ${paint}/>`;
  return `<svg class="graph-legend-shape" viewBox="0 0 20 20" width="22" height="22" aria-hidden="true">${body}</svg>`;
}

function renderGraphLegend() {
  const { nodes } = filteredGraph({ applyHidden: false });
  const counts = new Map();
  for (const node of nodes) counts.set(node.type, (counts.get(node.type) || 0) + 1);
  const types = [...counts.keys()].sort((a, b) => {
    const ia = LEGEND_ORDER.indexOf(a);
    const ib = LEGEND_ORDER.indexOf(b);
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
  });

  const title = document.createElement("p");
  title.className = "graph-legend-title";
  title.innerHTML = `Key <span>click to hide a type</span>`;

  const lines = document.createElement("div");
  lines.className = "graph-line-key";
  lines.innerHTML = `
    <p class="graph-legend-title">Lines <span>confidence of the claim</span></p>
    <p><svg width="34" height="8" aria-hidden="true"><line x1="1" y1="4" x2="33" y2="4" stroke="#172018" stroke-opacity=".55" stroke-width="2"/></svg> Tier A–B</p>
    <p><svg width="34" height="8" aria-hidden="true"><line x1="1" y1="4" x2="33" y2="4" stroke="#172018" stroke-opacity=".55" stroke-width="2" stroke-dasharray="6 4"/></svg> Tier C</p>
    <p><svg width="34" height="8" aria-hidden="true"><line x1="1" y1="4" x2="33" y2="4" stroke="#172018" stroke-opacity=".55" stroke-width="2.4" stroke-dasharray="1 4" stroke-linecap="round"/></svg> Tier D</p>`;

  graphLegend.replaceChildren(
    title,
    ...types.map((type) => {
      const style = styleOf(type);
      const hidden = hiddenTypes.has(type);
      const item = document.createElement("button");
      item.type = "button";
      item.className = "graph-legend-item";
      item.dataset.hidden = String(hidden);
      item.setAttribute("aria-pressed", String(!hidden));
      item.title = style.blurb;
      item.innerHTML =
        `${shapeSvg(style.shape, style.color)}` +
        `<span class="graph-legend-text"><span class="graph-legend-name">${esc(style.name)} <span class="graph-count">${counts.get(type)}</span></span>` +
        `<span class="graph-legend-blurb">${esc(style.blurb)}</span></span>`;
      item.addEventListener("click", () => {
        if (hiddenTypes.has(type)) hiddenTypes.delete(type);
        else hiddenTypes.add(type);
        renderGraph();
      });
      return item;
    }),
    lines,
  );
}

// Tuned so ~200 nodes settle without piling on top of each other -- more repulsion/spacing than
// cytoscape's defaults, and nodeDimensionsIncludeLabels so a shown label counts toward its footprint.
const GRAPH_LAYOUT = {
  name: "cose",
  animate: false,
  fit: true,
  padding: 32,
  nodeDimensionsIncludeLabels: true,
  nodeRepulsion: () => 16000,
  idealEdgeLength: () => 100,
  edgeElasticity: () => 100,
  nodeOverlap: 24,
  componentSpacing: 120,
  gravity: 0.6,
  numIter: 2000,
  coolingFactor: 0.97,
  minTemp: 1.0,
};

function graphLayout() {
  return cy.layout(GRAPH_LAYOUT);
}

function resetGraphHighlight() {
  if (!cy) return;
  cy.elements().removeClass("highlighted dimmed show-label");
  graphDetail.hidden = true;
}

function chipRow(items) {
  const chip = (item) => `<button type="button" class="node-chip" data-node-id="${esc(item.id)}">${esc(item.label)}</button>`;
  const head = items.slice(0, 12).map(chip).join("");
  if (items.length <= 12) return `<div class="chip-row">${head}</div>`;
  return `<div class="chip-row">${head}</div><details class="chip-more"><summary>Show ${items.length - 12} more</summary><div class="chip-row">${items.slice(12).map(chip).join("")}</div></details>`;
}

// Coverage of one disease across the WHOLE knowledge base (not just the filtered view), so a
// reader can see at a glance what is documented and what is still missing.
function diseaseCoverage(diseaseId) {
  const count = (claimType, side) =>
    graphCache.edges.filter((e) => e.claim_type === claimType && e[side] === diseaseId).length;
  const row = (n, yes, no) => `<li data-ok="${n > 0}">${n > 0 ? `✓ ${yes(n)}` : `✗ ${no}`}</li>`;
  return `
    <p class="detail-subhead">What the knowledge base holds for this disease</p>
    <ul class="coverage-list">
      ${row(count("DISEASE_CAUSED_BY", "subject_id"), () => "Cause identified", "Cause not recorded")}
      ${row(count("DISEASE_ENV_TRIGGER", "subject_id"), () => "Weather trigger", "No weather trigger yet")}
      ${row(count("DISEASE_MANAGED_BY", "subject_id"), () => "Management advisory", "No advisory yet")}
      ${row(count("GENE_CONFERS_RESISTANCE", "object_id"), (n) => `${n} resistance gene${n > 1 ? "s" : ""}`, "No resistance genes yet")}
      ${row(count("VARIETY_REACTION", "object_id"), (n) => `${n} variet${n > 1 ? "ies" : "y"} with a documented reaction`, "No variety reactions yet")}
    </ul>`;
}

function buildNodeDetail(node) {
  const style = styleOf(node.data("type"));
  const groups = new Map();
  for (const edge of node.connectedEdges()) {
    const outgoing = edge.source().id() === node.id();
    const other = outgoing ? edge.target() : edge.source();
    const info = claimInfo(edge.data("claimType"));
    const key = `${edge.data("claimType")}|${outgoing ? "out" : "in"}`;
    if (!groups.has(key)) groups.set(key, { heading: outgoing ? info.out : info.inn, items: [] });
    groups.get(key).items.push({ id: other.id(), label: other.data("label") });
  }
  const sections = [...groups.values()]
    .sort((a, b) => b.items.length - a.items.length)
    .map((group) => {
      group.items.sort((a, b) => a.label.localeCompare(b.label));
      return `<section class="detail-group"><h4>${esc(group.heading)} <span class="graph-count">${group.items.length}</span></h4>${chipRow(group.items)}</section>`;
    });

  return `
    <h3>${esc(node.data("label"))} <span class="type-chip" style="--chip:${style.color}">${esc(style.name)}</span></h3>
    <p class="edge-meta">${esc(style.blurb)}</p>
    ${node.data("type") === "Advisory" && node.data("props") ? `<p class="edge-meta"><strong>${esc(node.data("props").action_type ?? "")}</strong> practice</p>${advisoryFacts(node.data("props"))}` : ""}
    ${node.data("type") === "EnvTrigger" && node.data("props") ? triggerFacts(node.data("props")) : ""}
    ${node.data("type") === "Disease" ? diseaseCoverage(node.id()) : ""}
    ${sections.length ? `<p class="detail-subhead">Connected in the current view — click any name to jump to it</p>${sections.join("")}` : ""}
  `;
}

function showNodeDetail(node) {
  cy.elements().addClass("dimmed").removeClass("highlighted show-label");
  const neighborhood = node.closedNeighborhood();
  neighborhood.removeClass("dimmed");
  neighborhood.nodes().addClass("show-label");
  node.addClass("highlighted");

  graphDetail.hidden = false;
  graphDetail.innerHTML = buildNodeDetail(node);
  for (const chip of graphDetail.querySelectorAll("[data-node-id]")) {
    chip.addEventListener("click", () => focusNode(chip.dataset.nodeId));
  }
  graphDetail.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

// A claim's own panel: the sentence it states, how confident we are and why, and its sources.
function showEdgeDetail(edge) {
  cy.elements().addClass("dimmed").removeClass("highlighted show-label");
  const ends = edge.connectedNodes();
  edge.removeClass("dimmed");
  ends.removeClass("dimmed").addClass("show-label");

  const info = claimInfo(edge.data("claimType"));
  const claim = {
    tier: edge.data("tier"),
    score: edge.data("score"),
    n_sources: edge.data("nSources"),
    conflict: edge.data("conflict"),
  };
  graphDetail.hidden = false;
  graphDetail.innerHTML = `
    <h3>${esc(edge.source().data("label"))} ${esc(info.verb)} ${esc(edge.target().data("label"))}</h3>
    <p class="edge-meta">${tierChip(claim) || "No confidence tier is computed for this claim."}
    ${claim.tier ? ` &nbsp; ${esc(TIER_MEANING[claim.tier] ?? "")}.` : ""}</p>
    ${claim.n_sources === 1 ? `<p class="edge-meta">This claim rests on a single source — the tier reflects that source's evidence type, not independent confirmation.</p>` : ""}
    <p class="detail-subhead">Sources</p>
    <div class="evidence-body"></div>`;
  renderEvidenceInto(graphDetail.querySelector(".evidence-body"), edge.id());
  graphDetail.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

function focusNode(id) {
  if (!cy) return;
  const node = cy.getElementById(id);
  if (node.empty()) return;
  cy.animate({ center: { eles: node }, zoom: Math.max(cy.zoom(), 1.1) }, { duration: 250 });
  showNodeDetail(node);
}

function positionTooltip(evt) {
  const containerRect = graphCanvas.getBoundingClientRect();
  const original = evt.originalEvent;
  let x, y;
  if (original && typeof original.clientX === "number") {
    x = original.clientX - containerRect.left;
    y = original.clientY - containerRect.top;
  } else {
    const rendered = evt.target.renderedPosition ? evt.target.renderedPosition() : evt.target.renderedMidpoint();
    x = rendered.x;
    y = rendered.y;
  }
  graphTooltip.style.left = `${x}px`;
  graphTooltip.style.top = `${y}px`;
}

function showTooltip(evt, html) {
  graphTooltip.innerHTML = html;
  graphTooltip.hidden = false;
  positionTooltip(evt);
}

function hideTooltip() {
  graphTooltip.hidden = true;
}

function renderGraph() {
  if (!graphCache) return;
  const { nodes, edges } = filteredGraph();
  setStatus(graphStatusText, `${nodes.length} entities / ${edges.length} claims`, "ready");
  renderGraphLegend();
  graphDetail.hidden = true;
  graphEmpty.hidden = nodes.length > 0;
  hideTooltip();

  const degree = new Map();
  for (const e of edges) {
    degree.set(e.subject_id, (degree.get(e.subject_id) || 0) + 1);
    degree.set(e.object_id, (degree.get(e.object_id) || 0) + 1);
  }

  const elements = [
    ...nodes.map((n) => {
      const style = styleOf(n.type);
      const deg = degree.get(n.id) || 0;
      return {
        data: {
          id: n.id,
          label: n.name,
          type: n.type,
          color: style.color,
          ring: darken(style.color, 0.6),
          shape: style.shape,
          size: style.size + Math.min(12, Math.round(2.4 * Math.sqrt(deg))),
          anchor: Boolean(style.anchor),
          props: n.props || null,
          deg,
        },
      };
    }),
    ...edges.map((e) => ({
      data: {
        id: e.claim_id,
        source: e.subject_id,
        target: e.object_id,
        claimType: e.claim_type,
        tier: e.tier ?? "",
        score: e.score,
        nSources: e.n_sources,
        conflict: Boolean(e.conflict),
      },
    })),
  ];

  if (!cy) {
    cy = window.cytoscape({
      container: graphCanvas,
      elements,
      style: [
        {
          selector: "node",
          style: {
            shape: "data(shape)",
            "background-color": "data(color)",
            width: "data(size)",
            height: "data(size)",
            label: "",
            color: "#172018",
            "font-size": "10px",
            "text-valign": "bottom",
            "text-margin-y": 4,
            "text-background-color": "#fbfaf6",
            "text-background-opacity": 0.88,
            "text-background-padding": "2px",
            "min-zoomed-font-size": 7,
            "border-width": 1.5,
            "border-color": "data(ring)",
          },
        },
        // Crops and diseases are the landmarks: always labelled so the graph can be read without
        // hovering. Everything else is labelled on hover or inside a clicked node's neighbourhood.
        {
          selector: "node[?anchor]",
          style: {
            label: "data(label)",
            "font-size": "15px",
            "font-weight": 700,
            "text-wrap": "wrap",
            "text-max-width": "120px",
            "min-zoomed-font-size": 5,
          },
        },
        { selector: "node.show-label, node.hovered", style: { label: "data(label)", "z-index": 20 } },
        {
          selector: "edge",
          style: {
            width: 1.2,
            "line-color": "rgba(23,32,24,0.22)",
            "target-arrow-color": "rgba(23,32,24,0.34)",
            "target-arrow-shape": "triangle",
            "arrow-scale": 0.7,
            "curve-style": "bezier",
          },
        },
        // Line style carries the claim's confidence tier: solid A/B, dashed C, dotted D.
        { selector: "edge[tier = 'C']", style: { "line-style": "dashed", "line-dash-pattern": [6, 4] } },
        { selector: "edge[tier = 'D']", style: { "line-style": "dotted", "line-dash-pattern": [2, 4], "line-cap": "round" } },
        { selector: "edge[?conflict]", style: { "line-color": "#a61b2a", "target-arrow-color": "#a61b2a" } },
        { selector: "node.highlighted", style: { "border-width": 3.5, "border-color": "#172018" } },
        { selector: "node.dimmed, edge.dimmed", style: { opacity: 0.12 } },
        { selector: "edge.hovered", style: { "line-color": "#172018", "target-arrow-color": "#172018", width: 2.4, opacity: 1 } },
      ],
      layout: GRAPH_LAYOUT,
      minZoom: 0.15,
      maxZoom: 4,
      wheelSensitivity: 0.2,
    });

    cy.on("tap", "node", (evt) => showNodeDetail(evt.target));
    cy.on("tap", "edge", (evt) => showEdgeDetail(evt.target));
    cy.on("tap", (evt) => {
      if (evt.target === cy) resetGraphHighlight();
    });
    cy.on("mouseover", "node", (evt) => {
      const node = evt.target;
      node.addClass("hovered");
      const deg = node.data("deg");
      showTooltip(evt, `<strong>${esc(node.data("label"))}</strong><br>${esc(styleOf(node.data("type")).name)} · ${deg} claim${deg === 1 ? "" : "s"}<br><em>click for details</em>`);
    });
    cy.on("mouseout", "node", (evt) => {
      evt.target.removeClass("hovered");
      hideTooltip();
    });
    cy.on("mousemove", "node", positionTooltip);
    cy.on("mouseover", "edge", (evt) => {
      const edge = evt.target;
      edge.addClass("hovered");
      const verb = claimInfo(edge.data("claimType")).verb;
      const tier = edge.data("tier");
      showTooltip(
        evt,
        `<strong>${esc(edge.source().data("label"))}</strong> ${esc(verb)} <strong>${esc(edge.target().data("label"))}</strong>` +
          (tier ? `<br>Tier ${esc(tier)} · ${plural(edge.data("nSources") ?? 0, "source")}` : "") +
          `<br><em>click for the evidence</em>`,
      );
    });
    cy.on("mouseout", "edge", (evt) => {
      evt.target.removeClass("hovered");
      hideTooltip();
    });
    cy.on("mousemove", "edge", positionTooltip);
  } else {
    cy.elements().remove();
    cy.add(elements);
    graphLayout().run();
  }
}

function zoomGraphBy(factor) {
  if (!cy) return;
  const width = graphCanvas.clientWidth;
  const height = graphCanvas.clientHeight;
  const level = Math.max(cy.minZoom(), Math.min(cy.maxZoom(), cy.zoom() * factor));
  cy.animate({ zoom: { level, renderedPosition: { x: width / 2, y: height / 2 } } }, { duration: 150 });
}

graphCropSelect.addEventListener("change", () => {
  updateDiseaseOptions();
  renderGraph();
});
graphDiseaseSelect.addEventListener("change", renderGraph);
graphZoomIn.addEventListener("click", () => zoomGraphBy(1.35));
graphZoomOut.addEventListener("click", () => zoomGraphBy(1 / 1.35));
graphZoomFit.addEventListener("click", () => cy && cy.animate({ fit: { eles: cy.elements(), padding: 32 } }, { duration: 200 }));

// ---------------------------------------------------------------------------
// Initialise
// ---------------------------------------------------------------------------

loadVarietiesInto(cropSelect, varietySelect, (t, s) => setStatus(reactionStatusText, t, s));
loadVarietiesInto(triggerCropSelect, triggerVarietySelect);
loadStats();
initTour({ showTab, whenGraphReady });
