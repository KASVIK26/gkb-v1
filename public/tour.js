// Guided product tour (driver.js). Switches tabs as it goes so every step highlights something visible.

const SEEN_KEY = "agrihub-tour-seen-v1";

function hasSeenTour() {
  try {
    return localStorage.getItem(SEEN_KEY) === "1";
  } catch {
    return false; // storage blocked (private mode etc.) -- the tour then simply offers itself each visit
  }
}

function markTourSeen() {
  try {
    localStorage.setItem(SEEN_KEY, "1");
  } catch {
    // nothing to do
  }
}

const STEPS = [
  {
    popover: {
      title: "Welcome to the AgriHub knowledge base",
      description:
        "A curated, cited map of crop-disease knowledge for <strong>wheat, soybean and chickpea</strong>: " +
        "which varieties resist which diseases, which genes confer that resistance, what weather favours each " +
        "disease, and how to manage it. This short tour shows what each view does.",
    },
  },
  {
    element: "#statsBar",
    needsVisible: true,
    popover: {
      title: "Live numbers",
      description:
        "These counts come straight from the live knowledge base. A <strong>claim</strong> is one cited statement, " +
        "such as “Sr33 confers resistance to stem rust”.",
    },
  },
  {
    element: "#mainTabs",
    popover: {
      title: "Three ways to explore",
      description:
        "<strong>Browse</strong> looks things up, <strong>Check sensor readings</strong> tests field conditions " +
        "against the trigger library, and <strong>Visualize</strong> shows everything as one connected graph.",
    },
  },
  {
    tab: "browse",
    element: "#browseControls",
    popover: {
      title: "Look up a variety",
      description: "Pick a crop and a variety, then press <strong>Search</strong>. Leave the variety on “All” to see the whole crop.",
    },
  },
  {
    tab: "browse",
    element: "#reactionsPanel",
    popover: {
      title: "Variety reactions",
      description:
        "Each card is one claim: the disease and how the variety reacts. The <strong>tier chip</strong> (A strongest, " +
        "D weakest) says how strong its evidence is, and <strong>Show evidence</strong> opens the paper or official " +
        "document it comes from.",
    },
  },
  {
    tab: "browse",
    element: "#genePanel",
    popover: {
      title: "Genes that protect the crop",
      description:
        "Pick a variety to see the genes it carries, how that was established (marker, postulation, stated), " +
        "which disease each gene protects against and which pathotypes defeat it. Where the KG holds no gene " +
        "for a variety the page says so rather than guessing; with “All varieties” it lists the crop-wide claims.",
    },
  },
  {
    tab: "browse",
    element: "#qtlPanel",
    popover: {
      title: "Genome regions (QTL)",
      description:
        "Where in the genome resistance has been mapped, for the selected crop: position, p-value or LOD, the study population and " +
        "the genes inside the region. They describe the crop, not one variety, and each card has its evidence.",
    },
  },
  {
    tab: "profiles",
    element: "#profileControls",
    popover: {
      title: "Profiles",
      description:
        "One page per variety, disease or gene: a variety's reactions, genes and zones; a disease's resistant varieties, genes, " +
        "genome regions, weather triggers, advisories and pathotype survey; a gene's diseases and carriers. Names are links, and " +
        "every statement shows its strength and evidence.",
    },
  },
  {
    tab: "triggers",
    element: "#demoWarning",
    popover: {
      title: "Check sensor readings",
      description:
        "Type field readings and see which disease triggers fire. <strong>Honest caveat:</strong> this is a " +
        "snapshot demo of the trigger library, not the real windowed risk engine.",
    },
  },
  {
    tab: "triggers",
    element: "#sensorGrid",
    popover: {
      title: "Fill in what you have",
      description:
        "Leave any reading blank — a blank is reported as “can’t evaluate”, never guessed. " +
        "Results also show the matching management advisory.",
    },
  },
  {
    tab: "graph",
    element: "#graphPresets",
    popover: {
      title: "Start with a question",
      description: "Each shortcut selects the right relationship types for you. “Show everything” resets the view.",
    },
  },
  {
    tab: "graph",
    element: ".graph-canvas-wrap",
    popover: {
      title: "The graph",
      description:
        "Every shape is an <strong>entity</strong>; every arrow is one <strong>cited claim</strong>. Solid lines are " +
        "strong evidence, dashed and dotted are weaker. <strong>Click an entity</strong> to see what it connects to " +
        "(a disease shows what is still missing), or <strong>click a line</strong> to see its sources.",
    },
  },
  {
    tab: "graph",
    element: "#graphLegend",
    popover: {
      title: "The key",
      description:
        "Colour <em>and</em> shape tell you the type, so it also works for colour-blind readers. " +
        "Click an item to hide that type — handy for decluttering the many varieties.",
      side: "left",
    },
  },
  {
    tab: "graph",
    element: "#graphControls",
    popover: {
      title: "Filters",
      description: "Narrow the graph by crop, by disease, or by relationship type.",
    },
  },
  {
    tab: "graph",
    element: ".graph-zoom-controls",
    popover: {
      title: "Zoom and fit",
      description: "Or scroll to zoom and drag to pan. ⤢ fits everything back on screen.",
      side: "left",
    },
  },
  {
    tab: "graph",
    element: "#graphConfidence",
    popover: {
      title: "Know what you are looking at",
      description:
        "Every claim cites a source and carries a tier A–D. This note always says how many sit in each tier, " +
        "how many rest on a single source, and how many have been human-reviewed.",
    },
  },
  {
    popover: {
      title: "You are set",
      description:
        "Replay this any time with <strong>Take the tour</strong> at the top. Good first stop: open " +
        "<strong>Visualize</strong> and click a disease.",
    },
  },
];

export function initTour({ showTab, whenGraphReady }) {
  const createDriver = window.driver?.js?.driver;
  const button = document.getElementById("tourButton");
  if (!createDriver) {
    // The CDN script was blocked or failed -- hide the entry point instead of leaving a dead button.
    button?.remove();
    return;
  }

  const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
  let steps = [];
  let tour = null;

  async function prepare(step) {
    if (!step) return;
    if (step.tab) showTab(step.tab);
    if (step.tab === "graph") await whenGraphReady();
  }

  function build() {
    steps = STEPS.filter((step) => {
      if (!step.needsVisible) return true;
      const el = document.querySelector(step.element);
      return Boolean(el) && !el.hidden;
    });
    tour = createDriver({
      steps,
      showProgress: true,
      progressText: "{{current}} of {{total}}",
      nextBtnText: "Next →",
      prevBtnText: "← Back",
      doneBtnText: "Finish",
      popoverClass: "agrihub-tour",
      overlayOpacity: 0.55,
      stagePadding: 8,
      stageRadius: 14,
      animate: !reducedMotion,
      smoothScroll: !reducedMotion,
      allowClose: true,
      onNextClick: async () => {
        if (tour.isLastStep()) {
          tour.destroy();
          return;
        }
        await prepare(steps[tour.getActiveIndex() + 1]);
        tour.moveNext();
      },
      onPrevClick: async () => {
        await prepare(steps[tour.getActiveIndex() - 1]);
        tour.movePrevious();
      },
      onDestroyed: markTourSeen,
    });
  }

  async function startTour() {
    if (tour?.isActive()) return;
    build();
    showTab("browse");
    window.scrollTo({ top: 0, behavior: reducedMotion ? "auto" : "smooth" });
    tour.drive();
  }

  button?.addEventListener("click", startTour);

  // First-time visitors get the tour automatically once; ?tour=1 forces it, ?tour=0 suppresses it.
  const flag = new URLSearchParams(window.location.search).get("tour");
  if (flag === "1" || (flag !== "0" && !hasSeenTour())) {
    setTimeout(startTour, 900);
  }
}
