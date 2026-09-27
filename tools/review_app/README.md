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

## Deploying (Streamlit Community Cloud)

No auth beyond whatever protects the URL — fine for a showcase, not for anything with real
reviewer accountability. If this needs real access control later, put it behind Cloudflare Access
(or an equivalent identity-aware proxy) in front of it.

1. Push this repo to GitHub (Streamlit Cloud deploys from a GitHub repo, not a local checkout).
2. At [share.streamlit.io](https://share.streamlit.io), create a new app pointing at this repo,
   branch `master`, main file path `tools/review_app/app.py`. It picks up
   `tools/review_app/requirements.txt` automatically (installs this repo editable with the
   `review` extra, so `curator` is importable for the Export tab's CLI call too).
3. In the app's **Settings → Secrets**, paste (TOML format):
   ```toml
   API_BASE_URL = "https://<your-api-service>.onrender.com"
   DATABASE_URL_DIRECT = "postgresql://...."   # only needed for the Export tab
   ```
   (`app.py` bridges `st.secrets` into `os.environ` on startup, so the existing
   `os.environ.get(...)` calls and the Export tab's subprocess both see these.)
4. Once deployed, go back to the `api/` service's CORS setting (`API_CORS_ORIGINS`) and add this
   app's `https://<name>.streamlit.app` origin, or extraction requests will be blocked by the
   browser's CORS check.

See the repo root's deployment guide for the `api/` service's own deployment (Render) and the
public dashboard's (Cloudflare Pages).
