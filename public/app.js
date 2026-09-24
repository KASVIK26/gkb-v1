// AgriHub KB — frontend controller
// E1: IoT toggle filter
// E2: Pathogen + source in edge cards
// E3: Stats bar populated from /api/stats

const cropSelect    = document.getElementById("cropSelect");
const varietySelect = document.getElementById("varietySelect");
const searchButton  = document.getElementById("searchButton");
const statusText    = document.getElementById("statusText");
const edgeList      = document.getElementById("edgeList");
const resultsPanel  = document.querySelector(".results");
const iotToggle     = document.getElementById("iotToggle");

// Stats bar elements (E3)
const statsBar      = document.getElementById("statsBar");
const statEdges     = document.getElementById("statEdges");
const statGenes     = document.getElementById("statGenes");
const statDiseases  = document.getElementById("statDiseases");
const statVarieties = document.getElementById("statVarieties");
const statCrops     = document.getElementById("statCrops");

let isLoadingVarieties = false;
let isQuerying = false;

// Store last fetched edges so the IoT toggle can re-filter without a new fetch
let lastEdges = [];

// ---------------------------------------------------------------------------
// UI state helpers
// ---------------------------------------------------------------------------

function setStatus(text, state = "idle") {
  statusText.textContent = text;
  statusText.dataset.state = state;
}

function setResultsState(state) {
  resultsPanel.dataset.state = state;
}

function updateControlState() {
  varietySelect.disabled = isLoadingVarieties;
  searchButton.disabled = isLoadingVarieties || isQuerying;
}

function setVarietyOptions(varieties, selectedValue = "__all__") {
  const options = [
    { label: "All varieties", value: "__all__" },
    ...varieties.map((v) => ({ label: v, value: v })),
  ];

  varietySelect.replaceChildren(
    ...options.map((opt) => {
      const el = document.createElement("option");
      el.value = opt.value;
      el.textContent = opt.label;
      return el;
    }),
  );

  const values = options.map((o) => o.value);
  varietySelect.value = values.includes(selectedValue) ? selectedValue : "__all__";
}

function setVarietyLoadingOption() {
  const opt = document.createElement("option");
  opt.value = "__all__";
  opt.textContent = "Loading varieties...";
  varietySelect.replaceChildren(opt);
}

// ---------------------------------------------------------------------------
// Stats bar (E3)
// ---------------------------------------------------------------------------

async function loadStats() {
  try {
    const response = await fetch("/api/stats");
    if (!response.ok) return; // stats are a nice-to-have; fail silently
    const data = await response.json();
    statEdges.textContent    = data.edges     ?? "—";
    statGenes.textContent    = data.genes     ?? "—";
    statDiseases.textContent = data.diseases  ?? "—";
    statVarieties.textContent = data.varieties ?? "—";
    statCrops.textContent    = data.crops     ?? "—";
    statsBar.hidden = false;
  } catch {
    // If /api/stats isn't deployed yet, the bar stays hidden — no error shown.
  }
}

// ---------------------------------------------------------------------------
// Variety loader
// ---------------------------------------------------------------------------

async function loadVarieties() {
  const previousSelection = varietySelect.value;

  isLoadingVarieties = true;
  updateControlState();
  setVarietyLoadingOption();
  setStatus("Loading varieties...", "loading");

  try {
    const response = await fetch(`/api/varieties?crop=${encodeURIComponent(cropSelect.value)}`);
    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.error || "Could not load varieties");
    }

    setVarietyOptions(payload.varieties || [], previousSelection);
    setStatus(`${payload.count || 0} variet${payload.count === 1 ? "y" : "ies"}`, "ready");
  } catch (error) {
    setVarietyOptions([]);
    setStatus("Error", "error");
    setResultsState("error");
    edgeList.innerHTML = `<div class="edge-card edge-card-error"><h3>Could not load varieties</h3><p class="edge-meta">${error.message}</p></div>`;
  } finally {
    isLoadingVarieties = false;
    updateControlState();
  }
}

// ---------------------------------------------------------------------------
// Edge rendering — E1 (IoT filter) + E2 (pathogen / source)
// ---------------------------------------------------------------------------

function confidenceBadge(confidence) {
  if (!confidence) return "";
  return `<span class="confidence-badge" data-level="${confidence}">${confidence}</span>`;
}

function iotBadge(iotTrigger) {
  if (!iotTrigger) return "";
  return `<span class="iot-badge" title="IoT trigger: ${iotTrigger}">📡 IoT</span>`;
}

function renderEdges(edges) {
  edgeList.innerHTML = "";
  setResultsState("ready");

  // E1: apply IoT filter
  const filtered = iotToggle.checked
    ? edges.filter((e) => e.iotTrigger && e.iotTrigger.trim())
    : edges;

  if (!filtered.length) {
    const msg = iotToggle.checked && edges.length
      ? "No edges with an IoT trigger for this selection. Uncheck the filter to see all results."
      : "The backend answered, but no resistance edges matched this crop/variety combination.";
    edgeList.innerHTML = `<div class="edge-card"><h3>No results</h3><p class="edge-meta">${msg}</p></div>`;
    return;
  }

  for (const edge of filtered) {
    const card = document.createElement("article");
    card.className = "edge-card";

    // E2: include pathogen and source
    const pathogenLine = edge.pathogen
      ? `<p class="edge-meta"><em>${edge.pathogen}</em></p>`
      : "";

    const iotLine = edge.iotTrigger
      ? `<p class="edge-meta">IoT trigger: ${edge.iotTrigger}</p>`
      : "";

    const sourceLine = edge.source
      ? `<p class="edge-source">Source: ${edge.source}</p>`
      : "";

    card.innerHTML = `
      <h3>
        ${edge.gene ?? "—"} → ${edge.disease ?? "—"}
        ${confidenceBadge(edge.confidence)}
        ${iotBadge(edge.iotTrigger)}
      </h3>
      ${pathogenLine}
      <p class="edge-meta">
        Chromosome: ${edge.chromosome ?? "n/a"} &nbsp;|&nbsp;
        Allele: ${edge.allele ?? "n/a"} &nbsp;|&nbsp;
        Type: ${edge.resistanceType ?? "n/a"}
      </p>
      <p class="edge-meta">
        Treatment: ${edge.treatment ?? "n/a"}
      </p>
      ${iotLine}
      ${sourceLine}
    `;
    edgeList.appendChild(card);
  }
}

// ---------------------------------------------------------------------------
// Query runner
// ---------------------------------------------------------------------------

async function runQuery() {
  setStatus("Loading...", "loading");
  setResultsState("loading");
  isQuerying = true;
  updateControlState();

  try {
    const response = await fetch("/api/query", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        crop: cropSelect.value,
        variety: varietySelect.value,
      }),
    });

    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.error || "Query failed");
    }

    lastEdges = payload.edges || [];
    renderEdges(lastEdges);

    const visibleCount = iotToggle.checked
      ? lastEdges.filter((e) => e.iotTrigger).length
      : lastEdges.length;
    setStatus(`${visibleCount} edge(s)`, "ready");
  } catch (error) {
    lastEdges = [];
    setStatus("Error", "error");
    setResultsState("error");
    edgeList.innerHTML = `<div class="edge-card edge-card-error"><h3>Query failed</h3><p class="edge-meta">${error.message}</p></div>`;
  } finally {
    isQuerying = false;
    updateControlState();
  }
}

// ---------------------------------------------------------------------------
// Event listeners
// ---------------------------------------------------------------------------

cropSelect.addEventListener("change", loadVarieties);
searchButton.addEventListener("click", runQuery);

// E1: re-render from cache when toggle changes (no re-fetch)
iotToggle.addEventListener("change", () => {
  if (lastEdges.length > 0) {
    renderEdges(lastEdges);
    const visibleCount = iotToggle.checked
      ? lastEdges.filter((e) => e.iotTrigger).length
      : lastEdges.length;
    setStatus(`${visibleCount} edge(s)`, "ready");
  }
});

// ---------------------------------------------------------------------------
// Initialise
// ---------------------------------------------------------------------------

setStatus("Ready", "idle");
setResultsState("ready");
renderEdges([]);
loadVarieties();
loadStats(); // E3: populate stats bar
