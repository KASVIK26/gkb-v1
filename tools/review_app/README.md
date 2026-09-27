# Paper-extraction review app

A local Streamlit tool for the human-review step of the paper-extraction pipeline
(RESEARCH_ROADMAP.md task 5.10, TECH_STACK.md M9). It talks to the `api/` FastAPI service over
HTTP only — no direct database or LLM access from here, so all trust logic (grounding,
normalization, what gets staged) lives in exactly one place.

## Run locally

Two processes, both from the repo root:

```bash
# 1. the API service (needs DATABASE_URL_DIRECT and OPEN_ROUTER_API_KEY in your environment/.env)
./.venv/Scripts/python.exe -m uvicorn api.main:app --reload

# 2. the review app
./.venv/Scripts/python.exe -m streamlit run tools/review_app/app.py
```

Install the extra dependency groups first if you haven't:

```bash
./.venv/Scripts/python.exe -m pip install -e ".[api,review]"
```

By default the app looks for the API at `http://localhost:8000`; override with the `API_BASE_URL`
environment variable if you're running it elsewhere.

## What it does

- **Extract** — pick a crop, give a PMID or DOI, and it runs the full pipeline (Europe PMC
  verification → LLM extraction → quote grounding → entity normalization → an LLM opinion on the
  source's relevance/credibility) and stages every accepted candidate in Postgres.
- **Review queue** — approve or reject each staged candidate. Nothing here touches the live
  knowledge graph.
- **Export** — turns every approved candidate into a `kg/curated/*.yaml` file via
  `agrihub lit export-staged`. You still review the file, `git add` it, and run
  `agrihub kg build`/`kg load`/`kg promote` yourself — this only automates the typing.

## Deploying later

This is a local tool for now — no auth beyond whatever protects your machine. If it's ever
deployed somewhere reachable over the network, put it behind Cloudflare Access (or an equivalent
identity-aware proxy) in front of it, and lock the `api/` service's CORS allowlist down to that
deployment's origin. Neither of those is set up yet.
