const cropSelect = document.getElementById("cropSelect");
const varietySelect = document.getElementById("varietySelect");
const searchButton = document.getElementById("searchButton");
const statusText = document.getElementById("statusText");
const edgeList = document.getElementById("edgeList");
const resultsPanel = document.querySelector(".results");

let isLoadingVarieties = false;
let isQuerying = false;

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
    ...varieties.map((variety) => ({ label: variety, value: variety })),
  ];

  varietySelect.replaceChildren(
    ...options.map((option) => {
      const element = document.createElement("option");
      element.value = option.value;
      element.textContent = option.label;
      return element;
    }),
  );

  const values = options.map((option) => option.value);
  varietySelect.value = values.includes(selectedValue) ? selectedValue : "__all__";
}

function setVarietyLoadingOption() {
  const option = document.createElement("option");
  option.value = "__all__";
  option.textContent = "Loading varieties...";
  varietySelect.replaceChildren(option);
}

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

function renderEdges(edges) {
  edgeList.innerHTML = "";
  setResultsState("ready");

  if (!edges.length) {
    edgeList.innerHTML = '<div class="edge-card"><h3>No edges returned</h3><p class="edge-meta">The backend answered, but no resistance edges matched this crop/variety combination.</p></div>';
    return;
  }

  for (const edge of edges) {
    const card = document.createElement("article");
    card.className = "edge-card";
    card.innerHTML = `
      <h3>${edge.gene} → ${edge.disease}</h3>
      <p class="edge-meta">Chromosome: ${edge.chromosome ?? "n/a"} | Allele: ${edge.allele ?? "n/a"} | Confidence: ${edge.confidence ?? "n/a"}</p>
      <p class="edge-meta">Resistance type: ${edge.resistanceType ?? "n/a"} | Treatment: ${edge.treatment ?? "n/a"}</p>
    `;
    edgeList.appendChild(card);
  }
}

async function runQuery() {
  setStatus("Loading...", "loading");
  setResultsState("loading");
  isQuerying = true;
  updateControlState();

  try {
    const response = await fetch("/api/query", {
      method: "POST",
      headers: {
        "content-type": "application/json",
      },
      body: JSON.stringify({
        crop: cropSelect.value,
        variety: varietySelect.value,
      }),
    });

    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.error || "Query failed");
    }

    renderEdges(payload.edges || []);
    setStatus(`${(payload.edges || []).length} edge(s)`, "ready");
  } catch (error) {
    setStatus("Error", "error");
    setResultsState("error");
    edgeList.innerHTML = `<div class="edge-card edge-card-error"><h3>Query failed</h3><p class="edge-meta">${error.message}</p></div>`;
  } finally {
    isQuerying = false;
    updateControlState();
  }
}

cropSelect.addEventListener("change", loadVarieties);
searchButton.addEventListener("click", runQuery);
setStatus("Ready", "idle");
setResultsState("ready");
renderEdges([]);
loadVarieties();
