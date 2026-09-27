// AgriHub KB — frontend controller (rebuilt against the Postgres/Supabase KG, 2026-09-26)

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

for (const btn of tabButtons) {
  btn.addEventListener("click", () => {
    for (const b of tabButtons) b.setAttribute("aria-selected", String(b === btn));
    for (const [name, panel] of Object.entries(tabPanels)) {
      panel.dataset.active = String(name === btn.dataset.tab);
    }
    if (btn.dataset.tab === "graph") {
      if (!graphInitialized) {
        graphInitialized = true;
        loadGraphData();
      } else if (cy) {
        // The canvas was display:none while hidden -- cytoscape needs an explicit resize/fit.
        cy.resize();
        cy.fit();
      }
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

// Matches curator.model.enums.EntityType -- one color per node type, shown in the legend.
const NODE_COLORS = {
  Crop: "#8a6d3b",
  Variety: "#2f6b44",
  Gene: "#1f4e31",
  QTL: "#3d7a99",
  Marker: "#6a4f9c",
  RefGene: "#4a5b8c",
  Disease: "#a53c31",
  Pathogen: "#c76b2e",
  Pathotype: "#c76b2e",
  EnvTrigger: "#1a7a8c",
  AgroZone: "#7a8c1a",
  Advisory: "#2f6b44",
};
const DEFAULT_NODE_COLOR = "#5d6a61";

// Fetched once from /api/graph and kept here for the life of the page -- every filter change
// (crop, disease, relationship type) re-derives the visible subgraph from this cache instead of
// hitting the network again. This is the "fast, cache it, synchronous" requirement: at 210
// entities / 315 claims the full graph is small enough that client-side filtering is instant.
let graphCache = null;
let cy = null; // the cytoscape instance, created lazily on first activation of this tab

async function loadGraphData() {
  setStatus(graphStatusText, "Loading graph...", "loading");
  try {
    const response = await fetch("/api/graph");
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Could not load the graph");
    graphCache = payload;
    populateGraphFilters(payload);
    renderGraph();
  } catch (error) {
    setStatus(graphStatusText, "Error", "error");
    graphCanvas.innerHTML = `<div class="edge-card edge-card-error"><h3>Could not load the graph</h3><p class="edge-meta">${error.message}</p></div>`;
  }
}

function populateGraphFilters(payload) {
  const claimTypes = [...new Set(payload.edges.map((e) => e.claim_type))].sort();
  graphClaimTypesContainer.replaceChildren(
    ...claimTypes.map((type) => {
      const label = document.createElement("label");
      label.className = "graph-checkbox";
      label.innerHTML = `<input type="checkbox" value="${type}" checked /> ${type.replaceAll("_", " ").toLowerCase()}`;
      label.querySelector("input").addEventListener("change", renderGraph);
      return label;
    }),
  );
  updateDiseaseOptions();
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

function filteredGraph() {
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
  const nodes = graphCache.nodes.filter((n) => nodeIds.has(n.id));
  return { nodes, edges };
}

function renderGraphLegend(nodes) {
  const types = [...new Set(nodes.map((n) => n.type))].sort();
  graphLegend.replaceChildren(
    ...types.map((type) => {
      const item = document.createElement("span");
      item.className = "graph-legend-item";
      item.innerHTML = `<span class="graph-legend-swatch" style="background:${NODE_COLORS[type] || DEFAULT_NODE_COLOR}"></span>${type}`;
      return item;
    }),
  );
}

// Tuned so ~200 nodes settle without piling on top of each other -- more repulsion/spacing than
// cytoscape's defaults, and nodeDimensionsIncludeLabels so a node's (usually hidden) label still
// counts toward its footprint when one is shown.
const GRAPH_LAYOUT = {
  name: "cose",
  animate: false,
  fit: true,
  padding: 32,
  nodeDimensionsIncludeLabels: true,
  nodeRepulsion: () => 14000,
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

function showNodeDetail(node) {
  cy.elements().addClass("dimmed").removeClass("highlighted show-label");
  const neighborhood = node.closedNeighborhood();
  neighborhood.removeClass("dimmed");
  neighborhood.nodes().addClass("show-label");
  node.addClass("highlighted");

  const lines = node.connectedEdges().map((edge) => {
    const outgoing = edge.source().id() === node.id();
    const other = outgoing ? edge.target() : edge.source();
    return `<li>${outgoing ? "→" : "←"} <strong>${edge.data("claimLabel")}</strong> ${outgoing ? "→" : "←"} ${other.data("label")}</li>`;
  });

  graphDetail.hidden = false;
  graphDetail.innerHTML = `
    <h3>${node.data("label")} <span class="edge-meta">(${node.data("type")})</span></h3>
    <ul class="condition-list">${lines.join("")}</ul>
  `;
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
  setStatus(graphStatusText, `${nodes.length} node(s) / ${edges.length} edge(s)`, "ready");
  renderGraphLegend(nodes);
  graphDetail.hidden = true;
  hideTooltip();

  const elements = [
    ...nodes.map((n) => ({ data: { id: n.id, label: n.name, type: n.type } })),
    ...edges.map((e) => ({
      data: {
        id: e.claim_id,
        source: e.subject_id,
        target: e.object_id,
        claimLabel: e.claim_type.replaceAll("_", " ").toLowerCase(),
        claimType: e.claim_type,
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
            "background-color": (ele) => NODE_COLORS[ele.data("type")] || DEFAULT_NODE_COLOR,
            label: "",
            color: "#172018",
            "font-size": "10px",
            "text-valign": "bottom",
            "text-margin-y": 4,
            "text-background-color": "#fbfaf6",
            "text-background-opacity": 0.85,
            "text-background-padding": "2px",
            width: 16,
            height: 16,
            "border-width": 1,
            "border-color": "rgba(255,255,255,0.9)",
          },
        },
        // Labels stay off canvas by default (that was the main source of "text on text" clutter
        // at ~200 nodes) -- shown only on hover (.hovered) or for a clicked node's neighborhood
        // (.show-label), via the JS event handlers below.
        { selector: "node.show-label, node.hovered", style: { label: "data(label)" } },
        {
          selector: "edge",
          style: {
            width: 1.2,
            "line-color": "rgba(23,32,24,0.2)",
            "target-arrow-color": "rgba(23,32,24,0.3)",
            "target-arrow-shape": "triangle",
            "arrow-scale": 0.7,
            "curve-style": "bezier",
            // No on-canvas edge label -- with hundreds of edges the text just overlapped itself;
            // the relationship name shows in the hover tooltip and the click-detail list instead.
          },
        },
        { selector: "node.highlighted", style: { "border-width": 3, "border-color": "#2f6b44", width: 22, height: 22 } },
        { selector: "node.dimmed, edge.dimmed", style: { opacity: 0.12 } },
        { selector: "edge.hovered", style: { "line-color": "#2f6b44", "target-arrow-color": "#2f6b44", width: 2.2, opacity: 1 } },
      ],
      layout: GRAPH_LAYOUT,
      minZoom: 0.15,
      maxZoom: 4,
      wheelSensitivity: 0.2,
    });

    cy.on("tap", "node", (evt) => showNodeDetail(evt.target));
    cy.on("tap", (evt) => {
      if (evt.target === cy) resetGraphHighlight();
    });
    cy.on("mouseover", "node", (evt) => {
      evt.target.addClass("hovered");
      showTooltip(evt, `<strong>${evt.target.data("label")}</strong><br>${evt.target.data("type")}`);
    });
    cy.on("mouseout", "node", (evt) => {
      evt.target.removeClass("hovered");
      hideTooltip();
    });
    cy.on("mousemove", "node", positionTooltip);
    cy.on("mouseover", "edge", (evt) => {
      const edge = evt.target;
      edge.addClass("hovered");
      showTooltip(evt, `<strong>${edge.data("claimLabel")}</strong><br>${edge.source().data("label")} → ${edge.target().data("label")}`);
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
